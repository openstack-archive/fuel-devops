#class ControllerSingleton(Controller):
#    _instance = None
#
#    def __new__(cls, *args, **kwargs):
#        if not cls._instance:
#            cls._instance = super(ControllerSingleton, cls).__new__(
#                cls, *args, **kwargs)
#        return cls._instance

import argparse
import os
from devops.manager import Manager

class Shell(object):

    def __init__(self):
        super(Shell, self).__init__()
        self.params = self.get_params()
        self.manager = Manager()


    def execute(self):
        self.commands.get(self.params.command)()

        def do_list(self):
            pass

        def do_show(self):
            pass

        def do_erase(self):
            pass

        def do_suspend(self):
            pass

        def do_resume(self):
            pass

        def do_revert(self):
            pass

        def do_snapshot(self):
            pass

    commands = {
        'list' : 'do_list',
        'show': 'do_show',
        'erase': 'do_erase',
        'suspend': 'do_suspend',
        'resume': 'do_resume',
        'revert': 'do_revert',
        'snapshot': 'do_snapshot'
    }

    def get_params(self):
        parser = argparse.ArgumentParser(description="Integration test suite")
        parser.add_argument('command',
            choices=self.commands.keys(),
            help="command to execute")
        parser.add_argument(
            '--name', metavar='<name>',
            default=os.environ.get('ENV_NAME'),
            help='Environment name')
        parser.add_argument(
            '--snapshot-name', metavar='<snapshot-name>',
            default=os.environ.get('SNAPSHOT_NAME'),
            help='Snapshot name')
        return parser.parse_args()



