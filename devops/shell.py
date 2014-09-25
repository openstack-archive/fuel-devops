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
        command = self.params.command
        if command in self.commands:
            self.commands.get(command)(self)
        elif command in self.env_commands:
            environment = self.manager.environment_get(
                self.params.name,
                raise_exception=False)
            if environment:
                self.env_commands.get(command)(self, environment)
            else:
                print "Cannot remove '{0}': No such environment" . format(self.params.name)

    def do_list(self):
        env_list = self.manager.environment_list().values('name')
        for env in env_list:
            print(env['name'])

        return env_list

    def node_dict(self, node):
        return {'name': node.name,
                'vnc': node.get_vnc_port()}

    def do_show(self, environment):
        print('%5s %25s' % ("VNC", "NODE-NAME"))
        for item in map(lambda x: self.node_dict(x), environment.nodes):
            print ('%5s %25s' % (item['vnc'], item['name']))

    def do_erase(self, environment):
        environment.erase()

    def do_start(self, environment):
        environment.start()

    def do_destroy(self, environment):
        environment.destroy(verbose=False)

    def do_suspend(self, environment):
        environment.suspend(verbose=False)

    def do_resume(self, environment):
        environment.resume(verbose=False)

    def do_revert(self, environment):
        environment.revert(self.params.snapshot_name)

    def do_snapshot(self, environment):
        environment.snapshot(self.params.snapshot_name)

    def do_synchronize(self):
        self.manager.synchronize_environments(self.params.remove)

    def do_snapshot_list(self, environment):
        snap_nodes = {}
        max_len = 0
        for node in environment.nodes:
            snaps = sorted(node.get_snapshots())
            for snap in snaps:
                if len(snap) > max_len:
                    max_len = len(snap)
                if snap in snap_nodes:
                    snap_nodes[snap].append(node.name)
                else:
                    snap_nodes[snap] = [node.name, ]

        print("%*s     %50s" % (max_len, "SNAPSHOT", "NODES-NAME"))
        for snap in snap_nodes:
            print("%*s     %50s" % (max_len, snap,
                                    ', '.join(snap_nodes[snap])))

    def do_snapshot_delete(self, environment):
        for node in environment.nodes:
            snaps = sorted(node.get_snapshots())
            if self.params.snapshot_name in snaps:
                node.erase_snapshot(name=self.params.snapshot_name)

    def do_net_list(self, environment):
        networks = environment.networks
        print("%15s   %10s" % ("NETWORK NAME", "IP NET"))
        for network in networks:
            print("%15s  %10s" % (network.name, network.ip_network))

    commands = {
        'list': do_list,
        'sync': do_synchronize,
    }

    env_commands = {
        'show': do_show,
        'erase': do_erase,
        'start': do_start,
        'destroy': do_destroy,
        'suspend': do_suspend,
        'resume': do_resume,
        'revert': do_revert,
        'snapshot': do_snapshot,
        'snapshot-list': do_snapshot_list,
        'snapshot-delete': do_snapshot_delete,
        'net-list': do_net_list,
    }

    def get_params(self):
        name_parser = argparse.ArgumentParser(add_help=False)
        name_parser.add_argument('name', help='environment name',
                                 default=environ.get('ENV_NAME'),
                                 metavar='ENV_NAME')
        snapshot_name_parser = argparse.ArgumentParser(add_help=False)
        snapshot_name_parser.add_argument('--snapshot-name',
                                          help='snapshot name',
                                          default=environ.get('SNAPSHOT_NAME'))
        sync_options = argparse.ArgumentParser(add_help=False)
        sync_options.add_argument('--remove',
                                  help='Remove undefined in devops VMs',
                                  action='store_true',
                                  default=False)
        parser = argparse.ArgumentParser(
            description="Manage virtual environments. "
                        "For addional help use command with -h/--help")
        subparsers = parser.add_subparsers(title="Operation commands",
                                           help='available commands',
                                           dest='command')
        subparsers.add_parser('list',
                              help="Show virtual environments",
                              description="Show virtual environments on host")
        subparsers.add_parser('show', parents=[name_parser],
                              help="Show VMs in environment",
                              description="Show VMs in environment")
        subparsers.add_parser('erase', parents=[name_parser],
                              help="Delete environment",
                              description="Delete environment and VMs on it")
        subparsers.add_parser('start', parents=[name_parser],
                              help="Start VMs",
                              description="Start VMs in selected environment")
        subparsers.add_parser('destroy', parents=[name_parser],
                              help="Destroy(stop) VMs",
                              description="Stop VMs in selected environment")
        subparsers.add_parser('suspend', parents=[name_parser],
                              help="Suspend VMs",
                              description="Suspend VMs in selected "
                              "environment")
        subparsers.add_parser('resume', parents=[name_parser],
                              help="Resume VMs",
                              description="Resume VMs in selected environment")
        subparsers.add_parser('revert',
                              parents=[name_parser, snapshot_name_parser],
                              help="Apply snapshot to environment",
                              description="Apply selected snapshot to "
                              "environment")
        subparsers.add_parser('snapshot',
                              parents=[name_parser, snapshot_name_parser],
                              help="Make environment snapshot",
                              description="Make environment snapshot")
        subparsers.add_parser('sync',
                              parents=[sync_options],
                              help="Synchronization environment and devops",
                              description="Synchronization environment "
                              "and devops"),
        subparsers.add_parser('snapshot-list',
                              parents=[name_parser],
                              help="Show snapshots in environment",
                              description="Show snapshots in selected "
                              "environment")
        subparsers.add_parser('snapshot-delete',
                              parents=[name_parser, snapshot_name_parser],
                              help="Delete snapshot from environment",
                              description="Delete snapshot from selected "
                              "environment")
        subparsers.add_parser('net-list',
                              parents=[name_parser],
                              help="Show networks in environment",
                              description="Display allocated networks for "
                              "environment")
        return parser.parse_args()
