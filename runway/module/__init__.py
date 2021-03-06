"""Runway module module."""
import logging
import os
import platform
import subprocess
import sys

import six

from ..util import merge_nested_environment_dicts, which

LOGGER = logging.getLogger('runway')
NPM_BIN = 'npm.cmd' if platform.system().lower() == 'windows' else 'npm'
NPX_BIN = 'npx.cmd' if platform.system().lower() == 'windows' else 'npx'


def format_npm_command_for_logging(command):
    """Convert npm command list to string for display to user."""
    if platform.system().lower() == 'windows':
        if command[0] == 'npx.cmd' and command[1] == '-c':
            return "npx.cmd -c \"%s\"" % " ".join(command[2:])
        return " ".join(command)
    # Strip out redundant npx quotes not needed when executing the command
    # directly
    return " ".join(command).replace('\'\'', '\'')


def generate_node_command(command, command_opts, path):
    """Return node bin command list for subprocess execution."""
    if which(NPX_BIN):
        # Use npx if available (npm v5.2+)
        LOGGER.debug("Using npx to invoke %s.", command)
        if platform.system().lower() == 'windows':
            cmd_list = [NPX_BIN,
                        '-c',
                        "%s %s" % (command, ' '.join(command_opts))]
        else:
            # The nested app-through-npx-via-subprocess command invocation
            # requires this redundant quoting
            cmd_list = [NPX_BIN,
                        '-c',
                        "''%s %s''" % (command, ' '.join(command_opts))]
    else:
        LOGGER.debug('npx not found; falling back invoking %s shell script '
                     'directly.', command)
        cmd_list = [
            os.path.join(path,
                         'node_modules',
                         '.bin',
                         command)
        ] + command_opts
    return cmd_list


def run_module_command(cmd_list, env_vars, exit_on_error=True):
    """Shell out to provisioner command."""
    if exit_on_error:
        try:
            subprocess.check_call(cmd_list, env=env_vars)
        except subprocess.CalledProcessError as shelloutexc:
            sys.exit(shelloutexc.returncode)
    else:
        subprocess.check_call(cmd_list, env=env_vars)


def use_npm_ci(path):
    """Return true if npm ci should be used in lieu of npm install."""
    # https://docs.npmjs.com/cli/ci#description
    with open(os.devnull, 'w') as fnull:
        if ((os.path.isfile(os.path.join(path,
                                         'package-lock.json')) or
             os.path.isfile(os.path.join(path,
                                         'npm-shrinkwrap.json'))) and
                subprocess.call(
                    [NPM_BIN, 'ci', '-h'],
                    stdout=fnull,
                    stderr=subprocess.STDOUT) == 0):
            return True
    return False


def run_npm_install(path, options, context):
    """Run npm install/ci."""
    # Use npm ci if available (npm v5.7+)
    if options.get('options', {}).get('skip_npm_ci'):
        LOGGER.info("Skipping npm ci or npm install on %s...",
                    os.path.basename(path))
    elif context.env_vars.get('CI') and use_npm_ci(path):
        LOGGER.info("Running npm ci on %s...",
                    os.path.basename(path))
        subprocess.check_call([NPM_BIN, 'ci'])
    else:
        LOGGER.info("Running npm install on %s...",
                    os.path.basename(path))
        subprocess.check_call([NPM_BIN, 'install'])


def warn_on_boto_env_vars(env_vars):
    """Inform user if boto-specific environment variables are in use."""
    # https://github.com/serverless/serverless/issues/2151#issuecomment-255646512
    if env_vars.get('AWS_DEFAULT_PROFILE') and not (
            env_vars.get('AWS_PROFILE')):
        LOGGER.warning('AWS_DEFAULT_PROFILE environment variable is set '
                       'during use of nodejs-based module and AWS_PROFILE is '
                       'not set -- you likely want to set AWS_PROFILE instead')


class RunwayModule(object):
    """Base class for Runway modules."""

    def __init__(self, context, path, options=None):
        """Initialize base class."""
        self.context = context

        self.path = path

        if options is None:
            self.options = {}
        else:
            self.options = options

    # the rest of these 'abstract' methods must have names which match
    #  the commands defined in `cli.py`

    def plan(self):
        """Implement dummy method (set in consuming classes)."""
        raise NotImplementedError('You must implement the plan() method '
                                  'yourself!')

    def deploy(self):
        """Implement dummy method (set in consuming classes)."""
        raise NotImplementedError('You must implement the deploy() method '
                                  'yourself!')

    def destroy(self):
        """Implement dummy method (set in consuming classes)."""
        raise NotImplementedError('You must implement the destroy() method '
                                  'yourself!')


class ModuleOptions(six.moves.collections_abc.MutableMapping):  # pylint: disable=no-member
    """Base class for Runway module options."""

    @staticmethod
    def merge_nested_env_dicts(data, env_name=None):
        """Merge nested env dicts.

        Args:
            data (Any): Data to try to merge.
            env_name (Optional[str]): Current environment.

        Returns:
            Any

        """
        if isinstance(data, (list, type(None), six.string_types)):
            return data
        if isinstance(data, dict):
            return {key: merge_nested_environment_dicts(value, env_name)
                    for key, value in data.items()}
        raise TypeError('expected type of list, NoneType, or str; '
                        'got type %s' % type(data))

    @classmethod
    def parse(cls, context, **kwargs):
        """Parse module options definition to extract usable options.

        Args:
            context (Context): Runway context object.

        """
        raise NotImplementedError

    def __delitem__(self, key):
        # type: (str) -> None
        """Implement deletion of self[key].

        Args:
            key: Attribute name to remove from the object.

        Example:
            .. codeblock: python

                obj = ModuleOptions(**{'key': 'value'})
                del obj['key']
                print(obj.__dict__)
                # {}

        """
        delattr(self, key)

    def __getitem__(self, key):
        """Implement evaluation of self[key].

        Args:
            key: Attribute name to return the value for.

        Returns:
            The value associated with the provided key/attribute name.

        Raises:
            KeyError: Key does not exist in the object.

        Example:
            .. codeblock: python

                obj = ModuleOptions(**{'key': 'value'})
                print(obj['key'])
                # value

        """
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def __setitem__(self, key, value):
        """Implement assignment to self[key].

        Args:
            key: Attribute name to associate with a value.
            value: Value of a key/attribute.

        Example:
            .. codeblock: python

                obj = ModuleOptions()
                obj['key'] = 'value'
                print(obj['key'])
                # value

        """
        setattr(self, key, value)

    def __len__(self):
        # type: () -> int
        """Implement the built-in function len().

        Example:
            .. codeblock: python

                obj = ModuleOptions(**{'key': 'value'})
                print(len(obj))
                # 1

        """
        return len(self.__dict__)

    def __iter__(self):
        """Return iterator object that can iterate over all attributes.

        Example:
            .. codeblock: python

                obj = ModuleOptions(**{'key': 'value'})
                for k, v in obj.items():
                    print(f'{key}: {value}')
                # key: value

        """
        return iter(self.__dict__)
