"""The run-aws command."""

import logging
import os

from awscli.clidriver import create_clidriver

from ..runway_command import RunwayCommand
from ...util import strip_leading_option_delim


def aws_cli(*cmd):
    """Invoke aws command."""
    old_env = dict(os.environ)
    try:

        # Environment
        env = os.environ.copy()
        env['LC_CTYPE'] = u'en_US.UTF'
        os.environ.update(env)

        # Run awscli in the same process
        exit_code = create_clidriver().main(*cmd)

        # Deal with problems
        if exit_code and exit_code > 0:
            raise RuntimeError('AWS CLI exited with code {}'.format(exit_code))
    finally:
        os.environ.clear()
        os.environ.update(old_env)


class RunAws(RunwayCommand):
    """Extend RunwayCommand with execution of awscli."""

    def execute(self):
        """Execute awscli."""
        if not os.environ.get('DEBUG'):
            for i in ['awscli.clidriver', 'awscli.formatter']:
                logging.getLogger(i).setLevel(logging.ERROR)
        cmd_line_args = strip_leading_option_delim(
            self._cli_arguments.get('<awscli-args>', [])
        )
        aws_cli(cmd_line_args)