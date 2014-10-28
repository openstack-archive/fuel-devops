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
import sys
from os import environ
import ipaddr
import time

from devops.manager import Manager

from helpers.helpers import sync_node_time
from helpers.helpers import _get_file_size
from helpers.helpers import _get_keys
from helpers.helpers import wait


class Shell(object):
    def __init__(self):
        super(Shell, self).__init__()
        self.params = self.get_params()
        self.manager = Manager()
        import logging
        l = logging.getLogger('django.db.backends')
        l.setLevel(logging.DEBUG)
        l.addHandler(logging.StreamHandler())

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

    def do_erase(self):
        self.manager.environment_get(self.params.name).erase()

    def do_start(self):
        env = self.manager.environment_get(self.params.name)
        if self.params.node_name is not None:
            env.node_by_name(self.params.node_name).start()
        else:
            env.start()

    def do_destroy(self):
        env = self.manager.environment_get(self.params.name)
        if self.params.node_name is not None:
            env.node_by_name(self.params.node_name).destroy()
        else:
            env.destroy(verbose=False)

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

    def do_snapshot_list(self):
        environment = self.manager.environment_get(self.params.name)

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

    def do_snapshot_delete(self):
        environment = self.manager.environment_get(self.params.name)
        for node in environment.nodes:
            snaps = sorted(node.get_snapshots())
            if self.params.snapshot_name in snaps:
                node.erase_snapshot(name=self.params.snapshot_name)

    def do_net_list(self):
        environment = self.manager.environment_get(self.params.name)
        networks = environment.networks
        print("%15s   %10s" % ("NETWORK NAME", "IP NET"))
        for network in networks:
            print("%15s  %10s" % (network.name, network.ip_network))

    def do_timesync(self):
        env = self.manager.environment_get(self.params.name)
        if not self.params.node_name:
            _nodes = {node.name: node.get_vnc_port() for node in env.nodes}
            for node_name in sorted(_nodes.keys()):
                if _nodes[node_name] != '-1':
                    sync_node_time(env, node_name)
        else:
            sync_node_time(env, self.params.node_name)

    def do_revert_resume(self):
        self.manager.environment_get(self.params.name).revert(
            self.params.snapshot_name)
        self.manager.environment_get(self.params.name).resume(verbose=False)
        if not self.params.no_timesync:
            print('time synchronization is starting')
            self.do_timesync()

    def do_create(self):

        def create_network(name, env, has_dhcp=False, has_pxe=False,
                           forward='nat', pool=None):
            net = self.manager.network_create(name=name, environment=env,
                                              has_dhcp_server=has_dhcp,
                                              has_pxe_server=has_pxe,
                                              forward=forward,
                                              pool=pool)
            net.define()
            net.start()

        def create_all_networks(env, names_list=None, pool=None):
            if names_list is None:
                names_list = ('admin', 'public', 'managment',
                              'private', 'storage')
            for name in names_list:
                create_network(name, env, pool=pool)

        env_name = self.params.name
        if env_name in self.manager.environment_list():
            print("Please select another environment name")
        else:
            new_env = self.manager.environment_create(env_name)
            networks, prefix = self.params.net_pool.split(':')
            self.manager.default_pool = self.manager.create_network_pool(
                networks=[ipaddr.IPNetwork(networks)],
                prefix=int(prefix))
            create_all_networks(env=new_env)
            self.do_add_node()

    def do_add_node(self):

        def attach_network_if_exsit(env, node, net_name):
            net = env.network_by_name(net_name)
            if net is not None:
                self.manager.interface_create(net, node)

        def attach_node_to_networks(env, node, names_list=None):
            if names_list is None:
                names_list = ('admin', 'public', 'managment',
                              'private', 'storage')
            for i in names_list:
                attach_network_if_exsit(env, node, i)

        def attach_disk(env, node, name, capacity, format='qcow2',
                        device='disk', bus='virtio'):
            vol_name = "%s-%s" % (node.name, name)
            new_volume = self.manager.volume_create(name=vol_name,
                                                    capacity=capacity,
                                                    environment=env,
                                                    format=format)
            new_volume.define()
            return self.manager.node_attach_volume(node=node,
                                                   volume=new_volume,
                                                   device=device,
                                                   bus=bus)

        def attach_disks_to_node(env, node, disknames_capacity=None):
            if disknames_capacity is None:
                disknames_capacity = {
                    'system': 50*1024*1024*1024,
                    'cinder': 50*1024*1024*1024,
                    'swift': 50*1024*1024*1024,
                }

            for diskname, cap in disknames_capacity.iteritems():
                attach_disk(env, node, diskname, cap)

        env_name = self.params.name
        env = self.manager.environment_get(env_name)
        vcpu = self.params.vcpu_count
        ram = self.params.ram_size
        created_nodes = len(env.nodes)
        node_count = self.params.node_count
        if created_nodes == 0:
            node_name = "admin"
            node = self.manager.node_create(name=node_name,
                                            environment=env,
                                            vcpu=vcpu,
                                            memory=1536,
                                            boot=['hd', 'cdrom'])
            attach_node_to_networks(env, node)
            attach_disks_to_node(env=env, node=node,
                                 disknames_capacity={
                                     'system': 50*1024*1024*1024,
                                 })
            iso_path = self.params.iso_path
            cdrom = attach_disk(env=env, node=node,
                                name="iso",
                                capacity=_get_file_size(iso_path),
                                format='raw',
                                device='cdrom',
                                bus='ide')
            cdrom.volume.upload(iso_path)
            node.define()
            created_nodes = 1
        for node in xrange(created_nodes, created_nodes+node_count):
                node_name = "slave-%i" % (node)
                node = self.manager.node_create(name=node_name,
                                                environment=env,
                                                vcpu=vcpu,
                                                memory=ram)
                attach_node_to_networks(env, node)
                attach_disks_to_node(env, node)
                node.define()
        self.manager.synchronize_environments()

    def do_remove_node(self):
        env_name = self.params.name
        node_name = self.params.node_name
        env = self.manager.environment_get(env_name)
        node = env.node_by_name(node_name)
        self.manager.remove_node(node)

    def do_node_change(self):
        node_name = self.params.node_name
        env_name = self.params.name
        env = self.manager.environment_get(env_name)
        vcpu = self.params.vcpu_count
        ram = self.params.ram_size
        node = env.node_by_name(node_name)
        self.manager.change_node(node, vcpu=vcpu, memory=ram)

    def do_admin_setup(self):

        def wait_bootstrap(puppet_timeout, admin_node):
            print "Waiting while bootstrapping is in progress"
            log_path = "/var/log/puppet/bootstrap_admin_node.log"
            print "Puppet timeout set in %i" % puppet_timeout
            wait(
                lambda: not
                admin_node.remote('admin',
                                  login='root',
                                  password='r00tme').execute(
                    "grep 'Fuel node deployment complete' '%s'" % log_path
                )['exit_code'],
                timeout=(float(puppet_timeout))
            )

        env_name = self.params.name
        env = self.manager.environment_get(env_name)
        admin_node = env.node_by_name('admin')
        admin_node.destroy()
        disks = admin_node.disk_devices
        for disk in disks:
            if (disk.device == 'disk' and
                    disk.volume.name == 'admin-system' and
                    disk.volume.get_allocation() > 1024*1024):

                print "Erase system disk"
                disk.volume.erase()
                new_volume = self.manager.volume_create(
                    name="admin-system",
                    capacity=50*1024*1024*1024,
                    environment=env,
                    format='qcow2')

                new_volume.define()
                self.manager.node_attach_volume(
                    node=admin_node,
                    volume=new_volume,
                    target_dev=disk.target_dev)

        admin_node.start()
        admin_net = env.network_by_name('admin')
        keys = _get_keys(
            ip=admin_node.get_ip_address_by_network_name('admin'),
            mask=admin_net.netmask,
            gw=admin_net.router,
            hostname='nailgun.test.domain.local',
            nat_interface='',
            dns1='8.8.8.8',
            showmenu='no')
        print "Waiting for admin node to start up"
        wait(lambda: admin_node.driver.node_active(admin_node), 60)
        print "Proceed with installation"
        admin_node.send_keys(keys)
        admin_node.await("admin", timeout=10 * 60)
        wait_bootstrap(3000, admin_node)

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
        'create': do_create,
        'node-add': do_add_node,
        'node-change': do_node_change,
        'node-remove': do_remove_node,
        'admin-setup':  do_admin_setup,
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
        node_name_parser = argparse.ArgumentParser(add_help=False)
        node_name_parser.add_argument('--node-name',
                                      help='node name',
                                      default=None)
        no_timesync_parser = argparse.ArgumentParser(add_help=False)
        no_timesync_parser.add_argument('--no-timesync', dest='no_timesync',
                                        action='store_const', const=True,
                                        help='revert without timesync',
                                        default=False)
        iso_path_parser = argparse.ArgumentParser(add_help=False)
        iso_path_parser.add_argument('--iso-path', dest='iso_path',
                                     help='select Fuel ISO path')
        ram_parser = argparse.ArgumentParser(add_help=False)
        ram_parser.add_argument('--ram', dest='ram_size',
                                help='select node RAM size',
                                default=1024, type=int)
        vcpu_parser = argparse.ArgumentParser(add_help=False)
        vcpu_parser.add_argument('--vcpu', dest='vcpu_count',
                                 help='select node VCPU count',
                                 default=1, type=int)
        node_count = argparse.ArgumentParser(add_help=False)
        node_count.add_argument('--node-count', dest='node_count',
                                help='How much node will create',
                                default=1, type=int)
        net_pool = argparse.ArgumentParser(add_help=False)
        net_pool.add_argument('--net-pool', dest='net_pool',
                              help='Choice ip network pool (cidr)',
                              default="10.21.0.0/16:24", type=str)
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
        subparsers.add_parser('start', parents=[name_parser, node_name_parser],
                              help="Start VMs",
                              description="Start VMs in selected environment")
        subparsers.add_parser('destroy', parents=[name_parser,
                                                  node_name_parser],
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
                                          " sync time on VMs"),
        subparsers.add_parser('create',
                              parents=[name_parser, vcpu_parser,
                                       node_count, ram_parser,
                                       net_pool, iso_path_parser],
                              help="Create new environment",
                              description="Create one new environment with "
                              "master node and slaves"),
        subparsers.add_parser('node-add',
                              parents=[name_parser, node_count,
                                       ram_parser, vcpu_parser],
                              help="Add node",
                              description="Add new node to environment")
        subparsers.add_parser('node-change',
                              parents=[name_parser, node_name_parser,
                                       ram_parser, vcpu_parser],
                              help="Change node vcpu and memory config",
                              description="Change count of vcpus and memory")
        subparsers.add_parser('node-remove',
                              parents=[name_parser, node_name_parser],
                              help="Remove node from environment",
                              description="Remove selected node from "
                              "environment")
        subparsers.add_parser('admin-setup',
                              parents=[name_parser],
                              help="Setup admin node",
                              description="Setup admin node from iso")
        if len(sys.argv) == 1:
            sys.argv.append("-h")
        return parser.parse_args()
