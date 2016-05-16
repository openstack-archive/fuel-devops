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

# pylint: disable=redefined-builtin
from six.moves import xrange
# pylint: enable=redefined-builtin
import tabulate

import devops

from devops.error import DevopsObjNotFound
from devops.helpers.ntp import sync_time
from devops.helpers.templates import create_devops_config
from devops.helpers.templates import create_slave_config
from devops.helpers.templates import get_devops_config
from devops.models import Environment
from devops import settings


class Shell(object):
    def __init__(self, args):
        self.args = args
        self.params = self.get_params()
        if getattr(self.params, 'snapshot-name', None):
            self.snapshot_name = getattr(self.params, 'snapshot-name')
        if (getattr(self.params, 'name', None) and
                getattr(self.params, 'command', None) != 'create'):
            try:
                self.env = Environment.get(name=self.params.name)
            except DevopsObjNotFound:
                self.env = None
                sys.exit("Enviroment with name {} doesn't exist."
                         "".format(self.params.name))

    def execute(self):
        self.commands.get(self.params.command)(self)

    def print_table(self, headers, columns):
        print(tabulate.tabulate(columns, headers=headers,
                                tablefmt="simple"))

    def do_list(self):
        env_list = Environment.list_all().values('name', 'created')
        columns = []
        for env in env_list:
            column = collections.OrderedDict({'NAME': env['name']})
            if self.params.list_ips:
                cur_env = Environment.get(name=env['name'])
                admin_ip = ''
                if 'admin' in [node.name for node in cur_env.get_nodes()]:
                    admin_ip = (cur_env.get_node(name='admin').
                                get_ip_address_by_network_name('admin'))
                column['ADMIN IP'] = admin_ip
            if self.params.timestamps:
                column['CREATED'] = env['created'].strftime(
                    '%Y-%m-%d_%H:%M:%S')
            columns.append(column)

        self.print_table(headers="keys", columns=columns)

    def node_dict(self, node):
        return {'name': node.name,
                'vnc': node.get_vnc_port()}

    def do_show(self):
        headers = ("VNC", "NODE-NAME")
        columns = [(node.get_vnc_port(), node.name)
                   for node in self.env.get_nodes()]
        self.print_table(headers=headers, columns=columns)

    def do_erase(self):
        self.env.erase()

    def do_start(self):
        self.env.start()

    def do_destroy(self):
        self.env.destroy()

    def do_suspend(self):
        self.env.suspend()

    def do_resume(self):
        self.env.resume()

    def do_revert(self):
        self.env.revert(self.snapshot_name, flag=False)

    def do_snapshot(self):
        if self.env.has_snapshot(self.snapshot_name):
            sys.exit("Snapshot with name {0} already exists."
                     .format(self.snapshot_name))
        else:
            self.env.snapshot(self.snapshot_name)

    def do_synchronize(self):
        Environment.synchronize_all()

    def do_snapshot_list(self):
        snapshots = collections.OrderedDict()

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
                info.created.strftime('%Y-%m-%d %H:%M:%S'),
                ', '.join(nodes),
            ))

        self.print_table(columns=columns, headers=headers)

    def do_snapshot_delete(self):
        for node in self.env.get_nodes():
            snaps = [x.name for x in node.get_snapshots()]
            if self.snapshot_name in snaps:
                node.erase_snapshot(name=self.snapshot_name)

    def do_net_list(self):
        headers = ("NETWORK NAME", "IP NET")
        columns = [(net.name, net.ip_network)
                   for net in self.env.get_networks()]
        self.print_table(headers=headers, columns=columns)

    def do_timesync(self):
        if not self.params.node_name:
            nodes = [node.name for node in self.env.get_nodes()
                     if node.driver.node_active(node)]
        else:
            nodes = [self.params.node_name]
        cur_time = sync_time(self.env, nodes, skip_sync=True)
        for name in sorted(cur_time):
            print("Current time on '{0}' = {1}".format(name, cur_time[name]))

        print("Please wait for a few minutes while time is synchronized...")

        new_time = sync_time(self.env, nodes, skip_sync=False)
        for name in sorted(new_time):
            print("New time on '{0}' = {1}".format(name, new_time[name]))

    def do_revert_resume(self):
        self.env.revert(self.snapshot_name, flag=False)
        self.env.resume()
        if not self.params.no_timesync:
            print('Time synchronization is starting')
            self.do_timesync()

    def do_version(self):
        print(devops.__version__)

    def do_create(self):
        config = create_devops_config(
            boot_from='cdrom',
            env_name=self.params.name,
            admin_vcpu=self.params.admin_vcpu_count,
            admin_memory=self.params.admin_ram_size,
            admin_sysvolume_capacity=self.params.admin_disk_size,
            admin_iso_path=self.params.iso_path,
            nodes_count=self.params.node_count,
            numa_nodes=settings.HARDWARE['numa_nodes'],
            slave_vcpu=self.params.vcpu_count,
            slave_memory=self.params.ram_size,
            slave_volume_capacity=settings.NODE_VOLUME_SIZE,
            second_volume_capacity=self.params.second_disk_size,
            third_volume_capacity=self.params.third_disk_size,
            use_all_disks=settings.USE_ALL_DISKS,
            ironic_nodes_count=settings.IRONIC_NODES_COUNT,
            networks_bonding=settings.BONDING,
            networks_bondinginterfaces=settings.BONDING_INTERFACES,
            networks_multiplenetworks=settings.MULTIPLE_NETWORKS,
            networks_nodegroups=settings.NODEGROUPS,
            networks_interfaceorder=settings.INTERFACE_ORDER,
            networks_pools=dict(admin=self.params.net_pool.split(':'),
                                public=self.params.net_pool.split(':'),
                                management=self.params.net_pool.split(':'),
                                private=self.params.net_pool.split(':'),
                                storage=self.params.net_pool.split(':')),
            networks_forwarding=settings.FORWARDING,
            networks_dhcp=settings.DHCP,
            driver_enable_acpi=settings.DRIVER_PARAMETERS['enable_acpi'],
        )
        self._create_env_from_config(config)

    def do_create_env(self):
        config = get_devops_config(self.params.env_config_name)
        self._create_env_from_config(config)

    def _create_env_from_config(self, config):
        env_name = config['template']['devops_settings']['env_name']
        for env in Environment.list_all():
            if env.name == env_name:
                print("Please, set another environment name")
                raise SystemExit()

        self.env = Environment.create_environment(config)
        self.env.define()

        # Start all l2 network devices
        for group in self.env.get_groups():
            for net in group.get_l2_network_devices():
                net.start()

    def do_slave_add(self, force_define=True):
        group = self.env.get_group(name='default')
        node_count = self.params.node_count
        created_nodes = len(group.get_nodes())

        for node_num in xrange(created_nodes, created_nodes + node_count):
            node_name = "slave-{:02d}".format(node_num)
            slave_conf = create_slave_config(
                slave_name=node_name,
                slave_role='fuel_slave',
                slave_vcpu=self.params.vcpu_count,
                slave_memory=self.params.ram_size,
                slave_volume_capacity=settings.NODE_VOLUME_SIZE,
                second_volume_capacity=self.params.second_disk_size,
                third_volume_capacity=self.params.third_disk_size,
                interfaceorder=settings.INTERFACE_ORDER,
                numa_nodes=settings.HARDWARE['numa_nodes'],
                use_all_disks=True,
                networks_multiplenetworks=settings.MULTIPLE_NETWORKS,
                networks_nodegroups=settings.NODEGROUPS,
                networks_bonding=settings.BONDING,
                networks_bondinginterfaces=settings.BONDING_INTERFACES,
            )

            node = group.add_node(slave_conf)
            if force_define is True:
                for volume in node.get_volumes():
                    volume.define()
                node.define()

    def do_slave_remove(self):
        volumes = []
        for drive in self.env.get_node(
                name=self.params.node_name).disk_devices:
            volumes.append(drive.volume)
        self.env.get_node(name=self.params.node_name).remove()
        for volume in volumes:
            volume.erase()

    def do_slave_change(self):
        node = self.env.get_node(name=self.params.node_name)
        node.set_vcpu(vcpu=self.params.vcpu_count)
        node.set_memory(memory=self.params.ram_size)

    def do_admin_change(self):
        node = self.env.get_node(name="admin")
        node.set_vcpu(vcpu=self.params.admin_vcpu_count)
        node.set_memory(memory=self.params.admin_ram_size)

    def do_admin_setup(self):
        admin_node = self.env.get_node(name='admin')
        if admin_node.kernel_cmd is None:
            admin_node.kernel_cmd = admin_node.ext.get_kernel_cmd(
                boot_from=self.params.boot_from,
                wait_for_external_config='no',
                iface=self.params.iface)
        admin_node.bootstrap_and_wait()
        admin_node.deploy_wait()

        print("Setup complete.\n ssh {0}@{1}".format(
            settings.SSH_CREDENTIALS['login'],
            admin_node.get_ip_address_by_network_name(
                settings.SSH_CREDENTIALS['admin_network'])))

    def do_node_start(self):
        self.check_param_show_help(self.params.node_name)
        self.env.get_node(name=self.params.node_name).start()

    def do_node_destroy(self):
        self.check_param_show_help(self.params.node_name)
        self.env.get_node(name=self.params.node_name).destroy()

    def do_node_reset(self):
        self.check_param_show_help(self.params.node_name)
        self.env.get_node(name=self.params.node_name).reset()

    def check_param_show_help(self, parameter):
        if not parameter:
            self.args.append('-h')
            self.get_params()

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
        'version': do_version,
        'create': do_create,
        'create-env': do_create_env,
        'slave-add': do_slave_add,
        'slave-change': do_slave_change,
        'slave-remove': do_slave_remove,
        'admin-setup': do_admin_setup,
        'admin-change': do_admin_change,
        'node-start': do_node_start,
        'node-destroy': do_node_destroy,
        'node-reset': do_node_reset
    }

    def get_params(self):
        name_parser = argparse.ArgumentParser(add_help=False)

        name_parser.add_argument('name', help='environment name',
                                 default=os.environ.get('ENV_NAME'),
                                 metavar='ENV_NAME')
        env_config_name_parser = argparse.ArgumentParser(add_help=False)
        env_config_name_parser.add_argument('env_config_name',
                                            help='environment template name',
                                            default=os.environ.get(
                                                'DEVOPS_SETTINGS_TEMPLATE'))

        snapshot_name_parser = argparse.ArgumentParser(add_help=False)
        snapshot_name_parser.add_argument('snapshot-name',
                                          help='snapshot name',
                                          default=os.environ.get(
                                              'SNAPSHOT_NAME'))

        node_name_parser = argparse.ArgumentParser(add_help=False)
        node_name_parser.add_argument('--node-name', '-N',
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
                                       second_disk_size, third_disk_size],
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
    Shell(args).execute()
