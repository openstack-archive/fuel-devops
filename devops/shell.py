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
        print self.manager.environment_list().values('name')

    def node_dict(self, node):
        return {'name': node.name,
                'vnc': node.get_vnc_port(),
        }

    def do_show(self):
        environment = self.manager.environment_get(self.params.name)
        print {
            'name': environment.name,
            'nodes': map(lambda x: {'node': self.node_dict(x)},
                         environment.nodes)
        }

    def do_erase(self):
        self.manager.environment_get(self.params.name).erase()

    def do_start(self):
        self.manager.environment_get(self.params.name).start()

    def do_destroy(self):
        self.manager.environment_get(self.params.name).destroy(verbose=False)

    def do_suspend(self):
        self.manager.environment_get(self.params.name).suspend(verbose=False)

    def do_resume(self):
        self.manager.environment_get(self.params.name).resume(verbose=False)

    def do_revert(self):
        self.manager.environment_get(self.params.name).revert(
            self.params.snapshot_name)

    def do_snapshot(self):
        self.manager.environment_get(self.params.name).snapshot(
            self.params.snapshot_name)

    commands = {
        'list': do_list,
        'show': do_show,
        'erase': do_erase,
        'start': do_start,
        'destroy': do_destroy,
        'suspend': do_suspend,
        'resume': do_resume,
        'revert': do_revert,
        'snapshot': do_snapshot
    }

    def get_params(self):
        name_parser = argparse.ArgumentParser(add_help=False)
        name_parser.add_argument('name', help='environment name',
                                 default=os.getenv('ENV_NAME'))
        snapshot_name_parser = argparse.ArgumentParser(add_help=False)
        snapshot_name_parser.add_argument('--snapshot-name',
                                          help='snapshot name',
                                          default=os.getenv('SNAPSHOT_NAME'))
        parser = argparse.ArgumentParser(
            description="Manage virtual environments")
        subparsers = parser.add_subparsers(help='commands', dest='command')
        subparsers.add_parser('list')
        subparsers.add_parser('show', parents=[name_parser])
        subparsers.add_parser('erase', parents=[name_parser])
        subparsers.add_parser('start', parents=[name_parser])
        subparsers.add_parser('destroy', parents=[name_parser])
        subparsers.add_parser('suspend', parents=[name_parser])
        subparsers.add_parser('resume', parents=[name_parser])
        subparsers.add_parser('revert',
                              parents=[name_parser, snapshot_name_parser])
        subparsers.add_parser('snapshot',
                              parents=[name_parser, snapshot_name_parser])
        return parser.parse_args()
