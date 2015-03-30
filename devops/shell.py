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
import os

import devops
from devops.helpers.helpers import sync_node_time
from devops.models import Environment


class Shell(object):
    def __init__(self):
        self.params = self.get_params()
        if getattr(self.params, 'name', None):
            self.env = Environment.get(name=self.params.name)

    def execute(self):
        self.commands.get(self.params.command)(self)

    def do_list(self):
        env_list = Environment.list().values('name', 'created')
        for env in env_list:
            if self.params.list_ips:
                cur_env = Environment.get(name=env['name'])
                admin_ip = ''
                if 'admin' in [node.name for node in cur_env.get_nodes()]:
                    admin_ip = (cur_env.get_node(name='admin').
                                get_ip_address_by_network_name('admin'))
                print('{0}\t{1}'.format(env['name'], admin_ip))
            elif self.params.timestamps:
                created_text = env['created'].strftime('%Y-%m-%d_%H:%M:%S')
                print('{0} {1}'.format(env['name'], created_text))
            else:
                print(env['name'])

        return env_list

    def node_dict(self, node):
        return {'name': node.name,
                'vnc': node.get_vnc_port()}

    def do_show(self):
        print('%5s %25s' % ("VNC", "NODE-NAME"))
        for item in map(lambda x: self.node_dict(x), self.env.get_nodes()):
            print ('%5s %25s' % (item['vnc'], item['name']))

    def do_erase(self):
        self.env.erase()

    def do_start(self):
        self.env.start()

    def do_destroy(self):
        self.env.destroy(verbose=False)

    def do_suspend(self):
        self.env.suspend(verbose=False)

    def do_resume(self):
        self.env.resume(verbose=False)

    def do_revert(self):
        self.env.revert(self.params.snapshot_name, flag=False)

    def do_snapshot(self):
        self.env.snapshot(self.params.snapshot_name)

    def do_synchronize(self):
        Environment.synchronize_all()

    def do_snapshot_list(self):
        snap_nodes = {}
        max_len = 0
        for node in self.env.get_nodes():
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

    def do_snapshot_delete(self):
        for node in self.env.get_nodes():
            snaps = sorted(node.get_snapshots())
            if self.params.snapshot_name in snaps:
                node.erase_snapshot(name=self.params.snapshot_name)

    def do_net_list(self):
        print("%15s   %10s" % ("NETWORK NAME", "IP NET"))
        for network in self.env.get_networks():
            print("%15s  %10s" % (network.name, network.ip_network))

    def do_timesync(self):
        if not self.params.node_name:
             for node in self.env.get_nodes():
                 if node.driver.node_active(node):
                    datetime = sync_node_time(self.env, node.name)
                    print('Node [{0}]: {1}'.format(node.name, datetime))
        else:
            datetime = sync_node_time(self.env, self.params.node_name)
            print('Node [{0}]: {1}'.format(node_name, datetime))

    def do_revert_resume(self):
        self.env.revert(self.params.snapshot_name, flag=False)
        self.env.resume(verbose=False)
        if not self.params.no_timesync:
            print('time synchronization is starting')
            self.do_timesync()

    def do_version(self):
        print(devops.__version__)

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
        'snapshot-list': do_snapshot_list,
        'snapshot-delete': do_snapshot_delete,
        'net-list': do_net_list,
        'time-sync': do_timesync,
        'revert-resume': do_revert_resume,
        'version': do_version
    }

    def get_params(self):
        name_parser = argparse.ArgumentParser(add_help=False)
        name_parser.add_argument('name', help='environment name',
                                 default=os.environ.get('ENV_NAME'),
                                 metavar='ENV_NAME')
        snapshot_name_parser = argparse.ArgumentParser(add_help=False)
        snapshot_name_parser.add_argument('--snapshot-name',
                                          help='snapshot name',
                                          default=os.environ.get(
                                              'SNAPSHOT_NAME'))
        node_name_parser = argparse.ArgumentParser(add_help=False)
        node_name_parser.add_argument('--node-name',
                                      help='node name',
                                      default=None)
        no_timesync_parser = argparse.ArgumentParser(add_help=False)
        no_timesync_parser.add_argument('--no-timesync', dest='no_timesync',
                                        action='store_const', const=True,
                                        help='revert without timesync',
                                        default=False)
        list_ips_parser = argparse.ArgumentParser(add_help=False)
        list_ips_parser.add_argument('--ips', dest='list_ips',
                                     action='store_const', const=True,
                                     help='show admin node ip addresses',
                                     default=False)
        timestamps_parser = argparse.ArgumentParser(add_help=False)
        timestamps_parser.add_argument('--timestamps', dest='timestamps',
                                       action='store_const', const=True,
                                       help='show creation timestamps',
                                       default=False)
        parser = argparse.ArgumentParser(
            description="Manage virtual environments. "
                        "For addional help use command with -h/--help")
        subparsers = parser.add_subparsers(title="Operation commands",
                                           help='available commands',
                                           dest='command')
        subparsers.add_parser('list',
                              parents=[list_ips_parser, timestamps_parser],
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
        subparsers.add_parser('time-sync',
                              parents=[name_parser, node_name_parser],
                              help="Sync time on all env nodes",
                              description="Sync time on all active nodes "
                                          "of environment starting from "
                                          "admin")
        subparsers.add_parser('revert-resume',
                              parents=[name_parser, snapshot_name_parser,
                                       node_name_parser, no_timesync_parser],
                              help="Revert, resume, sync time on VMs",
                              description="Revert and resume VMs in selected"
                                          "environment, then"
                                          " sync time on VMs")
        subparsers.add_parser('version',
                              help="Show devops version")
        return parser.parse_args()
