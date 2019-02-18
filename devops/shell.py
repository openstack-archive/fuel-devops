#    Copyright 2013 - 2016 Mirantis, Inc.
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

from __future__ import print_function

import argparse
import collections
import os
import sys

import datetime
import tabulate

from six.moves import input

import devops
from devops import client
from devops import error
from devops.helpers import helpers
from devops import logger


class Shell(object):
    def __init__(self, args):
        self.args = args
        self.params = self.get_params()
        self.client = client.DevopsClient()
        self.env = None

        name = getattr(self.params, 'name', None)
        command = getattr(self.params, 'command', None)

        if name and command != 'create':
            self.env = self.client.get_env(name)

    def execute(self):
        command_name = 'do_{}'.format(self.params.command.replace('-', '_'))
        command_method = getattr(self, command_name)
        command_method()

    @staticmethod
    def print_table(headers, columns):
        if not columns:
            return
        print(tabulate.tabulate(columns, headers=headers,
                                tablefmt="simple"))

    @staticmethod
    def query_yes_no(question, default=None):
        """Ask a yes/no question via standard input and return the answer.

        If invalid input is given, the user will be asked until
        they acutally give valid input.

        Args:
            question(str):
                A question that is presented to the user.
            default(bool|None):
                The default value when enter is pressed with no value.
                When None, there is no default value and the query
                will loop.
        Returns:
            A bool indicating whether user has entered yes or no.

        Side Effects:
            Blocks program execution until valid input(y/n) is given.
        """
        yes_list = ["yes", "y"]
        no_list = ["no", "n"]

        default_dict = {  # default => prompt default string
            None: "[y/n]",
            True: "[Y/n]",
            False: "[y/N]",
        }
        default_str = default_dict[default]
        prompt_str = "{} {} ".format(question, default_str)

        while True:
            choice = input(prompt_str).lower()

            if not choice and default is not None:
                return default
            if choice in yes_list:
                return True
            if choice in no_list:
                return False

            notification_str = "Please respond with 'y' or 'n'"
            print(notification_str)

    def print_envs_table(self, env_names_list):
        columns = []
        for env_name in sorted(env_names_list):
            env = self.client.get_env(env_name)
            column = collections.OrderedDict()
            column['NAME'] = env.name
            if self.params.list_ips:
                if env.has_admin():
                    column['ADMIN IP'] = env.get_admin_ip()
                else:
                    column['ADMIN IP'] = ''
            if self.params.timestamps:
                column['CREATED'] = helpers.utc_to_local(env.created).strftime(
                    '%Y-%m-%d_%H:%M:%S')
            columns.append(column)

        self.print_table(headers='keys', columns=columns)

    def do_list(self):
        self.print_envs_table(self.client.list_env_names())

    def do_show(self):
        nodes = sorted(self.env.get_nodes(), key=lambda node: node.name)
        headers = ("VNC", "NODE-NAME", "GROUP-NAME")
        columns = [(node.get_vnc_port(), node.name, node.group.name)
                   for node in nodes]
        self.print_table(headers=headers, columns=columns)

    def do_show_resources(self):
        nodes = sorted(self.env.get_nodes(), key=lambda node: node.name)
        headers = ("NAME", "ROLE", "GROUP", "VCPU", "MEMORY,Gb", "STORAGE,Gb")
        total_vcpu = 0
        total_memory = 0
        total_storage = 0
        columns = list()
        for node in nodes:
            vcpu = 0
            memory = 0
            storage = 0

            if 'vcpu' in node.get_defined_params():
                vcpu = node.vcpu

            if 'memory' in node.get_defined_params():
                memory = node.memory

            volumes = node.get_volumes()
            for volume in volumes:
                if 'capacity' in volume.get_defined_params():
                    storage += int(volume.capacity)

            columns.append(
                (
                    node.name,
                    node.role,
                    node.group.name,
                    vcpu or '-',
                    memory or '-',
                    storage or '-',
                )
            )
            total_vcpu += vcpu
            total_memory += memory
            total_storage += storage

        columns.append(
            (
                "Total:",
                '',
                '',
                total_vcpu or '-',
                total_memory or '-',
                total_storage or '-',
            )
        )
        self.print_table(headers=headers, columns=columns)

    def do_erase(self):
        self.env.erase()

    def get_lifetime_delta(self):
        data = self.params.env_lifetime
        multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        if data[-1] not in multipliers:
            raise ValueError(
                'Value should end with '
                'one of "{}", got "{}"'.format(
                    " ".join(multipliers.keys()), data
                ))
        num = int(data[:-1])
        mul = data[-1]
        return datetime.timedelta(seconds=num*multipliers[mul])

    def get_old_environments(self):
        delta = self.get_lifetime_delta()
        # devops uses utc timestamps for BaseModel
        timestamp_now = datetime.datetime.utcnow()
        envs_to_erase = []
        for env_name in client.DevopsClient.list_env_names():
            env = client.DevopsClient.get_env(env_name)
            if (timestamp_now - env.created) > delta:
                envs_to_erase.append(env)
        return envs_to_erase

    def do_erase_old(self):
        envs_to_erase = self.get_old_environments()

        for env in envs_to_erase:
            print("Env '{}' will be erased!".format(env.name))

        if envs_to_erase:
            if not self.params.force_cleanup:
                answer = self.query_yes_no(
                    "The cleanup operation is destructive one, "
                    "all environments listed above will be erased. "
                    "DELETION CAN NOT BE UNDONE! Proceed? ",
                    default=False)
                if not answer:
                    print("Wise choice, aborting...")
                    sys.exit(0)
        else:
            print("Nothing to erase, exiting...")
            sys.exit(0)

        for env in envs_to_erase:
            print("Erasing '{}'...".format(env.name))
            env.erase()

    def do_list_old(self):
        env_names = [env.name for env in self.get_old_environments()]
        self.print_envs_table(env_names)

    def do_start(self):
        self.env.start()

    def do_destroy(self):
        self.env.destroy()

    def do_suspend(self):
        self.env.suspend()

    def do_resume(self):
        self.env.resume()

    def do_revert(self):
        self.env.revert(self.params.snapshot_name, flag=False, resume=False)

    def do_snapshot(self):
        self.env.snapshot(self.params.snapshot_name)

    def do_sync(self):
        self.client.synchronize_all()

    def do_snapshot_list(self):
        snapshots = collections.OrderedDict()

        # noinspection PyPep8Naming
        Snap = collections.namedtuple('Snap', ['info', 'nodes'])

        for node in self.env.get_nodes():
            for snap in node.get_snapshots():
                if snap.name in snapshots:
                    snapshots[snap.name].nodes.append(node.name)
                else:
                    snapshots[snap.name] = Snap(snap, [node.name, ])

        snapshots = sorted(snapshots.values(), key=lambda x: x.info.created)

        headers = ('SNAPSHOT', 'CREATED', 'NODES-NAMES')
        columns = []
        for info, nodes in snapshots:
            nodes.sort()
            columns.append((
                info.name,
                helpers.utc_to_local(
                    info.created).strftime('%Y-%m-%d %H:%M:%S'),
                ', '.join(nodes),
            ))

        self.print_table(columns=columns, headers=headers)

    def do_snapshot_delete(self):
        for node in self.env.get_nodes():
            snaps = [x.name for x in node.get_snapshots()]
            if self.params.snapshot_name in snaps:
                node.erase_snapshot(name=self.params.snapshot_name)

    def do_net_list(self):
        headers = ("NETWORK NAME", "IP NET")
        columns = [(net.name, net.ip_network)
                   for net in self.env.get_address_pools()]
        self.print_table(headers=headers, columns=columns)

    def do_slave_ip_list(self):
        address_pool_name = self.params.address_pool_name

        slave_ips = {}
        for l2dev in self.env.get_env_l2_network_devices():
            if l2dev.address_pool is None:
                continue
            if address_pool_name and \
                    l2dev.address_pool.name != address_pool_name:
                continue

            ap_slave_ips = []
            for node in self.env.get_nodes():
                try:
                    node.get_interface_by_network_name(l2dev.name)
                except devops.models.network.Interface.DoesNotExist:
                    # Skip if l2 network device is not attached to the node
                    continue

                if self.params.ip_only:
                    ap_slave_ips.append(
                        node.get_ip_address_by_network_name(l2dev.name))
                else:
                    ap_slave_ips.append(
                        "{0},{1}".format(
                            node.name,
                            node.get_ip_address_by_network_name(l2dev.name)))
            if ap_slave_ips:
                if l2dev.address_pool.name in slave_ips:
                    slave_ips[l2dev.address_pool.name] += ap_slave_ips
                else:
                    slave_ips[l2dev.address_pool.name] = ap_slave_ips

        if not slave_ips:
            sys.exit('No IPs were allocated for environment!')

        for ap, n_ips in sorted(slave_ips.items()):
            if address_pool_name:
                print(' '.join(n_ips))
            else:
                print(ap + ": " + ' '.join(n_ips))

    def do_time_sync(self):
        node_name = self.params.node_name
        skip_sync = (self.params.skip_sync or '').split(",")

        if node_name:
            node_names = [node_name]
        else:
            node_names = [node.name for node in self.env.get_active_nodes()
                          if node.name not in skip_sync]

        cur_time = self.env.get_curr_time(node_names)
        for name in sorted(cur_time):
            print('Current time on {0!r} = {1}'.format(name, cur_time[name]))

        print('Please wait for a few minutes while time is synchronized...')

        new_time = self.env.sync_time(node_names)
        for name in sorted(new_time):
            print("New time on '{0}' = {1}".format(name, new_time[name]))

    def do_revert_resume(self):
        self.env.revert(self.params.snapshot_name, flag=False, resume=True)
        if self.params.timesync:
            print('Time synchronization is starting')
            self.do_time_sync()

    @staticmethod
    def do_version():
        print(devops.__version__)

    def do_create(self):
        """Create env using cli parameters."""
        env = self.client.create_env(
            env_name=self.params.name,
            admin_iso_path=self.params.iso_path,
            admin_vcpu=self.params.admin_vcpu_count,
            admin_memory=self.params.admin_ram_size,
            admin_sysvolume_capacity=self.params.admin_disk_size,
            nodes_count=self.params.node_count,
            slave_vcpu=self.params.vcpu_count,
            slave_memory=self.params.ram_size,
            second_volume_capacity=self.params.second_disk_size,
            third_volume_capacity=self.params.third_disk_size,
            net_pool=self.params.net_pool.split(':'),
        )
        env.define()

    def do_create_env(self):
        """Create env using config file."""
        env = self.client.create_env_from_config(
            self.params.env_config_name)
        env.define()

    def do_slave_add(self):
        self.env.add_slaves(
            nodes_count=self.params.node_count,
            slave_vcpu=self.params.vcpu_count,
            slave_memory=self.params.ram_size,
            second_volume_capacity=self.params.second_disk_size,
            third_volume_capacity=self.params.third_disk_size,
        )

    def do_slave_remove(self):
        # TODO(astudenov): add positional argument instead of option
        node = self.env.get_node(name=self.params.node_name)
        node.remove()

    def do_slave_change(self):
        node = self.env.get_node(name=self.params.node_name)
        # TODO(astudenov): check if node is under libvirt controll
        node.set_vcpu(vcpu=self.params.vcpu_count)
        node.set_memory(memory=self.params.ram_size)

    def do_admin_change(self):
        node = self.env.get_node(name="admin")
        # TODO(astudenov): check if node is under libvirt controll
        node.set_vcpu(vcpu=self.params.admin_vcpu_count)
        node.set_memory(memory=self.params.admin_ram_size)

    def do_admin_setup(self):
        # start networks first
        for group in self.env.get_groups():
            group.start_networks()

        self.env.admin_setup(
            boot_from=self.params.boot_from,
            iface=self.params.iface)
        print('Setup complete.\n ssh {0}@{1}'.format(
            self.env.get_admin_login(),
            self.env.get_admin_ip()))

    def do_node_start(self):
        # ensure networks are running prior to starting a node
        for group in self.env.get_groups():
            group.start_networks()
        # TODO(astudenov): add positional argument instead of
        # checking that option is present
        self.check_param_show_help(self.params.node_name)
        self.env.get_node(name=self.params.node_name).start()

    def do_node_destroy(self):
        # TODO(astudenov): add positional argument instead of
        # checking that option is present
        self.check_param_show_help(self.params.node_name)
        self.env.get_node(name=self.params.node_name).destroy()

    def do_node_reset(self):
        # TODO(astudenov): add positional argument instead of
        # checking that option is present
        self.check_param_show_help(self.params.node_name)
        self.env.get_node(name=self.params.node_name).reset()

    def check_param_show_help(self, parameter):
        if not parameter:
            self.args.append('-h')
            self.get_params()

    def get_params(self):
        name_parser = argparse.ArgumentParser(add_help=False)

        name_parser.add_argument('name', help='environment name',
                                 default=os.environ.get('ENV_NAME'),
                                 metavar='ENV_NAME')
        group_name_parser = argparse.ArgumentParser(add_help=False)

        group_name_parser.add_argument('--group-name', help='group name',
                                       default='default')
        env_config_name_parser = argparse.ArgumentParser(add_help=False)
        env_config_name_parser.add_argument('env_config_name',
                                            help='environment template name',
                                            default=os.environ.get(
                                                'DEVOPS_SETTINGS_TEMPLATE'))

        snapshot_name_parser = argparse.ArgumentParser(add_help=False)
        snapshot_name_parser.add_argument('snapshot_name',
                                          help='snapshot name',
                                          default=os.environ.get(
                                              'SNAPSHOT_NAME'))

        node_name_parser = argparse.ArgumentParser(add_help=False)
        node_name_parser.add_argument('--node-name', '-N',
                                      help='node name',
                                      default=None)

        skip_sync_parser = argparse.ArgumentParser(add_help=False)
        skip_sync_parser.add_argument('--skip-sync', '-K',
                                      help='Comma-separated list of nodes '
                                           'to skip time-sync',
                                      default=None)
        timesync_parser = argparse.ArgumentParser(add_help=False)
        timesync_parser.add_argument('--timesync', dest='timesync',
                                     action='store_const', const=True,
                                     help='revert with timesync',
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
        iso_path_parser = argparse.ArgumentParser(add_help=False)
        iso_path_parser.add_argument('--iso-path', '-I', dest='iso_path',
                                     help='Set Fuel ISO path',
                                     required=True)
        admin_ram_parser = argparse.ArgumentParser(add_help=False)
        admin_ram_parser.add_argument('--admin-ram', dest='admin_ram_size',
                                      help='Select admin node RAM size (MB)',
                                      default=1536, type=int)
        admin_vcpu_parser = argparse.ArgumentParser(add_help=False)
        admin_vcpu_parser.add_argument('--admin-vcpu', dest='admin_vcpu_count',
                                       help='Select admin node VCPU count',
                                       default=2, type=int)
        change_admin_ram_parser = argparse.ArgumentParser(add_help=False)
        change_admin_ram_parser.add_argument('--admin-ram',
                                             dest='admin_ram_size',
                                             help='Select admin node RAM '
                                             'size (MB)',
                                             default=None, type=int)
        change_admin_vcpu_parser = argparse.ArgumentParser(add_help=False)
        change_admin_vcpu_parser.add_argument('--admin-vcpu',
                                              dest='admin_vcpu_count',
                                              help='Select admin node VCPU '
                                              'count',
                                              default=None, type=int)
        admin_disk_size_parser = argparse.ArgumentParser(add_help=False)
        admin_disk_size_parser.add_argument('--admin-disk-size',
                                            dest='admin_disk_size',
                                            help='Set admin node disk '
                                                 'size (GB)',
                                            default=50, type=int)
        admin_setup_iface_parser = argparse.ArgumentParser(add_help=False)
        admin_setup_iface_parser.add_argument('--iface',
                                              dest='iface',
                                              help='Static network interface '
                                                   'to use when configuring '
                                                   'the admin node. Should '
                                                   'be eth0 or enp0s3',
                                              default='enp0s3')
        admin_setup_boot_from_parser = argparse.ArgumentParser(add_help=False)
        admin_setup_boot_from_parser.add_argument(
            '--boot-from', dest='boot_from', default='cdrom',
            help='Set device to boot from for admin node. '
            'Should be cdrom or usb')
        ram_parser = argparse.ArgumentParser(add_help=False)
        ram_parser.add_argument('--ram', dest='ram_size',
                                help='Set node RAM size',
                                default=1024, type=int)
        vcpu_parser = argparse.ArgumentParser(add_help=False)
        vcpu_parser.add_argument('--vcpu', dest='vcpu_count',
                                 help='Set node VCPU count',
                                 default=1, type=int)

        change_ram_parser = argparse.ArgumentParser(add_help=False)
        change_ram_parser.add_argument('--ram', dest='ram_size',
                                       help='Set node RAM size',
                                       default=None, type=int)
        change_vcpu_parser = argparse.ArgumentParser(add_help=False)
        change_vcpu_parser.add_argument('--vcpu', dest='vcpu_count',
                                        help='Set node VCPU count',
                                        default=None, type=int)
        node_count = argparse.ArgumentParser(add_help=False)
        node_count.add_argument('--node-count', '-C', dest='node_count',
                                help='How many nodes will be created',
                                default=1, type=int)
        net_pool = argparse.ArgumentParser(add_help=False)
        net_pool.add_argument('--net-pool', '-P', dest='net_pool',
                              help='Set ip network pool (cidr)',
                              default="10.21.0.0/16:24", type=str)
        address_pool_name = argparse.ArgumentParser(add_help=False)
        address_pool_name.add_argument(
            '--address-pool-name', '-A',
            dest='address_pool_name',
            help='Specified address pool for printing IPs',
            default=None, type=str)
        ip_only_parser = argparse.ArgumentParser(add_help=False)
        ip_only_parser.add_argument('--ip-only', dest='ip_only',
                                    action='store_const', const=True,
                                    help='Print just IP addresses',
                                    default=False)
        second_disk_size = argparse.ArgumentParser(add_help=False)
        second_disk_size.add_argument('--second-disk-size',
                                      dest='second_disk_size',
                                      help='Allocate second disk for node '
                                           'with selected size(GB). '
                                           'If set to 0, the disk will not be '
                                           'allocated',
                                      default=50, type=int)
        third_disk_size = argparse.ArgumentParser(add_help=False)
        third_disk_size.add_argument('--third-disk-size',
                                     dest='third_disk_size',
                                     help='Allocate the third disk for node '
                                          'with selected size(GB). '
                                          'If set to 0, the disk will not be '
                                          'allocated',
                                     default=50, type=int)

        force_cleanup_parser = argparse.ArgumentParser(add_help=False)
        force_cleanup_parser.add_argument(
            '--force-cleanup',
            dest='force_cleanup',
            action='store_const', const=True,
            help='Do not ask confirmation for cleanup action.',
            default=False)

        env_lifetime = argparse.ArgumentParser(add_help=False)
        env_lifetime.add_argument(
            dest='env_lifetime',
            help='Erase environments older than given time interval. '
                 'Example:"45m", "12h", "3d"',
            default="", type=str)

        parser = argparse.ArgumentParser(
            description="Manage virtual environments. "
                        "For additional help, use with -h/--help option")
        subparsers = parser.add_subparsers(title="Operation commands",
                                           help='available commands',
                                           dest='command')
        subparsers.add_parser('list',
                              parents=[list_ips_parser, timestamps_parser],
                              help="Show virtual environments",
                              description="Show virtual environments on host")
        subparsers.add_parser('erase-old',
                              parents=[force_cleanup_parser,
                                       env_lifetime],
                              help="Cleanup old virtual environments",
                              description="Cleanup virtual environments on "
                                          "host")
        subparsers.add_parser('list-old',
                              parents=[env_lifetime, list_ips_parser,
                                       timestamps_parser],
                              help="Show virtual environments older than given"
                                   " lifetime interval",
                              description="Show old virtual "
                                          "environments on host")
        subparsers.add_parser('show', parents=[name_parser],
                              help="Show VMs in environment",
                              description="Show VMs in environment")
        subparsers.add_parser('show-resources', parents=[name_parser],
                              help=("Show resources consumed by VMs "
                                    "in environment"),
                              description=("Show resources consumed by VMs "
                                           "in environment"))
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
        subparsers.add_parser('slave-ip-list',
                              parents=[name_parser,
                                       address_pool_name,
                                       ip_only_parser],
                              help="Show slave node IPs in environment",
                              description="Display allocated IPs for "
                              "environment slave nodes")
        subparsers.add_parser('time-sync',
                              parents=[name_parser, node_name_parser,
                                       skip_sync_parser],
                              help="Sync time on all env nodes",
                              description="Sync time on all active nodes "
                                          "of environment starting from "
                                          "admin")
        subparsers.add_parser('revert-resume',
                              parents=[name_parser, snapshot_name_parser,
                                       node_name_parser, timesync_parser,
                                       skip_sync_parser],
                              help="Revert, resume, sync time on VMs",
                              description="Revert and resume VMs in selected"
                                          "environment, then optionally sync "
                                          "time on VMs (by default time is "
                                          "not synced, additional '--timesync'"
                                          " flag is required)")
        subparsers.add_parser('version',
                              help="Show devops version")
        subparsers.add_parser('create',
                              parents=[name_parser, vcpu_parser,
                                       node_count, ram_parser,
                                       net_pool, iso_path_parser,
                                       admin_disk_size_parser,
                                       admin_ram_parser,
                                       admin_vcpu_parser,
                                       second_disk_size,
                                       third_disk_size],
                              help="Create a new environment (DEPRECATED)",
                              description="Create an environment by using "
                                          "cli options"),
        subparsers.add_parser('create-env',
                              parents=[env_config_name_parser],
                              help="Create a new environment",
                              description="Create an environment from a "
                                          "template file"),
        subparsers.add_parser('slave-add',
                              parents=[name_parser, node_count,
                                       ram_parser, vcpu_parser,
                                       second_disk_size, third_disk_size,
                                       group_name_parser],
                              help="Add a node",
                              description="Add a new node to environment")
        subparsers.add_parser('slave-change',
                              parents=[name_parser, node_name_parser,
                                       change_ram_parser, change_vcpu_parser],
                              help="Change node VCPU and memory config",
                              description="Change count of VCPUs and memory")
        subparsers.add_parser('slave-remove',
                              parents=[name_parser, node_name_parser],
                              help="Remove node from environment",
                              description="Remove selected node from "
                              "environment")
        subparsers.add_parser('admin-setup',
                              parents=[name_parser, admin_setup_iface_parser,
                                       admin_setup_boot_from_parser],
                              help="Setup admin node",
                              description="Setup admin node from ISO")
        subparsers.add_parser('admin-change',
                              parents=[name_parser, change_admin_ram_parser,
                                       change_admin_vcpu_parser],
                              help="Change admin node VCPU and memory config",
                              description="Change count of VCPUs and memory "
                                          "for admin node")
        subparsers.add_parser('node-start',
                              parents=[name_parser, node_name_parser],
                              help="Start node in environment",
                              description="Start a separate node in "
                                          "environment")
        subparsers.add_parser('node-destroy',
                              parents=[name_parser, node_name_parser],
                              help="Destroy (power off) node in environment",
                              description="Destroy a separate node in "
                                          "environment")
        subparsers.add_parser('node-reset',
                              parents=[name_parser, node_name_parser],
                              help="Reset (restart) node in environment",
                              description="Reset a separate node in "
                                          "environment")
        if len(self.args) == 0:
            self.args = ['-h']
        return parser.parse_args(self.args)


def main(args=None):
    if args is None:
        args = sys.argv[1:]

    try:
        shell = Shell(args)
        shell.execute()
    except error.DevopsError as exc:
        logger.debug(exc, exc_info=True)
        sys.exit('Error: {}'.format(exc))
