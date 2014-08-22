#    Copyright 2013 - 2014 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import argparse
from os import environ

from devops.manager import Manager


class Shell(object):
    def __init__(self):
        super(Shell, self).__init__()
        self.params = self.get_params()
        self.manager = Manager()

    def execute(self):
        self.commands.get(self.params.command)(self)

    def do_list(self):
        env_list = self.manager.environment_list().values('name')
        for env in env_list:
            print(env['name'])

        return env_list

    def node_dict(self, node):
        return {'name': node.name,
                'vnc': node.get_vnc_port()}

    def do_show(self):
        environment = self.manager.environment_get(self.params.name)

        print('%5s %25s' % ("VNC", "NODE-NAME"))
        for item in map(lambda x: self.node_dict(x), environment.nodes):
            print ('%5s %25s' % (item['vnc'], item['name']))

        snap_nodes = {}
        for node in environment.nodes:
            snaps = sorted(node.get_snapshots())
            for snap in snaps:
                if snap in snap_nodes is True:
                    snap_nodes[snap].append(node.name)
                else:
                    snap_nodes[snap] = [node.name, ]
        print("\n")
        print('%80s' % "SNAPSHOTS")
        print("\n")
        print('%40s     %50s' % ("SNAPSHOT", "NODES-NAME"))
        for snap in snap_nodes:
            print('%40s     %50s' % (snap, ', '.join(snap_nodes[snap])))

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

    def do_synchronize(self):
        self.manager.synchronize_environments()

    def do_clean(self):
        environment = self.manager.environment_get(self.params.name)
        for node in environment.nodes:
            snaps = sorted(node.get_snapshots())
            if self.params.snapshot_name in snaps:
                node.erase_snapshot(name=self.params.snapshot_name)

    commands = {
        'list': do_list,
        'show': do_show,
        'erase': do_erase,
        'start': do_start,
        'destroy': do_destroy,
        'suspend': do_suspend,
        'resume': do_resume,
        'revert': do_revert,
        'snapshot': do_snapshot,
        'sync': do_synchronize,
        'clean': do_clean
    }

    def get_params(self):
        name_parser = argparse.ArgumentParser(add_help=False)
        name_parser.add_argument('name', help='environment name',
                                 default=environ.get('ENV_NAME'))
        snapshot_name_parser = argparse.ArgumentParser(add_help=False)
        snapshot_name_parser.add_argument('--snapshot-name',
                                          help='snapshot name',
                                          default=environ.get('SNAPSHOT_NAME'))
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
        subparsers.add_parser('sync')
        subparsers.add_parser('clean',
                              parents=[name_parser, snapshot_name_parser])
        return parser.parse_args()
