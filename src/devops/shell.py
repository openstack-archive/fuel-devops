import argparse
import os
from devops.manager import Manager

class Shell(object):

    def __init__(self):
        super(Shell, self).__init__()
        self.params = self.get_params()
        self.manager = Manager()

    def execute(self):
        self.commands.get(self.params.command)(self)

    def do_list(self):
        self.manager.list_environments()

    def do_show(self):
        self.manager.get_environment(self.params.name)

    def do_erase(self):
        self.manager.erase_environment(self.manager.get_environment(self.params.name))

    def do_suspend(self):
        self.manager.suspend_environment(self.manager.get_environment(self.params.name))

    def do_resume(self):
        self.manager.resume_environment(self.manager.get_environment(self.params.name))

    def do_revert(self):
        self.manager.revert_environment(self.manager.get_environment(self.params.name), self.params.snapshot_name)

    def do_snapshot(self):
        self.manager.snapshot_environment(self.manager.get_environment(self.params.name), self.params.snapshot_name)

    commands = {
        'list' : do_list,
        'show': do_show,
        'erase': do_erase,
        'suspend': do_suspend,
        'resume': do_resume,
        'revert': do_revert,
        'snapshot': do_snapshot
    }

    def get_params(self):
        name_parser = argparse.ArgumentParser(add_help=False)
        name_parser.add_argument('name', help='environment name', default=os.getenv('ENV_NAME'))
        snapshot_name_parser = argparse.ArgumentParser(add_help=False)
        snapshot_name_parser.add_argument('--snapshot-name', help='snapshot name', default=os.getenv('SNAPSHOT_NAME'))
        parser = argparse.ArgumentParser(description="Manage virtual environments")
        subparsers = parser.add_subparsers(help='commands')
        subparsers.add_parser('list')
        subparsers.add_parser('show', parents=[name_parser])
        subparsers.add_parser('erase', parents=[name_parser])
        subparsers.add_parser('suspend', parents=[name_parser])
        subparsers.add_parser('resume', parents=[name_parser])
        subparsers.add_parser('revert', parents=[name_parser, snapshot_name_parser])
        subparsers.add_parser('suspend', parents=[name_parser, snapshot_name_parser])
        return parser.parse_args()
