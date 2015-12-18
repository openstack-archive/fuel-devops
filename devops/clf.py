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


import collections
import logging
import os
import sys

import ipaddr


from devops.helpers.helpers import _get_file_size
from devops.helpers import node_manager
from devops.helpers.ntp import sync_time
from devops.models import Environment
from devops.models.network import Network
from devops import settings

from cliff.app import App
from cliff.command import Command
from cliff.commandmanager import CommandManager
from cliff.lister import Lister


class DevopsCli(App):
    log = logging.getLogger(__name__)

    def __init__(self):
        command = CommandManager('devopscli.app')
        super(DevopsCli, self).__init__(
            description='sample app',
            version='0.1',
            command_manager=command,
        )
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
            'slave-add': do_slave_add,
            'slave-remove': do_slave_remove,
            'slave-change': do_slave_change,
            'admin-setup': do_admin_setup,
            'admin-change': do_admin_change,
            'admin-add': do_admin_add,
            'node-start': do_node_start,
            'node-destroy': do_node_destroy,
            'node-reset': do_node_reset
        }
        for k, v in commands.iteritems():
            command.add_command(k, v)

    def initialize_app(self, argv):
        self.log.debug('initialize_app')

    def prepare_to_run_command(self, cmd):
        self.log.debug('prepare_to_run_command %s', cmd.__class__.__name__)

    def clean_up(self, cmd, result, err):
        self.log.debug('clean_up %s', cmd.__class__.__name__)
        if err:
            self.log.debug('got an error: %s', err)


class Error(Command):
    "Always raises an error"
    log = logging.getLogger(__name__)

    def take_action(self, parsed_args):
        self.log.info('causing error')
        raise RuntimeError('this is the expected exception')


class do_list(Lister):
    "show list of resources"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_list, self).get_parser(prog_name)
        parser.add_argument('--ips', default=False, action='store_true',
                            help='show admin node ip addresses')
        parser.add_argument('--timestamps', default=False, action='store_true',
                            help='show creation timestamps')
        return parser

    def take_action(self, parsed_args):
        headers = ["NAME"]
        if parsed_args.ips:
                headers.append('ADMIN_IP')
        if parsed_args.timestamps:
                headers.append('CREATED')

        # self.log.info("ips={}".format(parsed_args.ips))
        self.app.stdout.write(
            "ips={}, timestamps={}".format(parsed_args.ips,
                                           parsed_args.timestamps))
        env_list = get_envs()
        records = []
        for env in env_list:
            admin_ip = ''
            timestamp = ''
            record = [env['name']]
            if parsed_args.ips:
                cur_env = get_env(env.get('name'))
                if 'admin' in [node.name for node in cur_env.get_nodes()]:
                    admin_ip = (cur_env.get_node(name='admin').
                                get_ip_address_by_network_name('admin'))
            if parsed_args.timestamps:
                timestamp = env['created'].strftime('%Y-%m-%d_%H:%M:%S')
            if admin_ip:
                record.append(admin_ip)
            if timestamp:
                record.append(timestamp)
            records.append(record)
        return (headers, records)


class do_show(Lister):
    "show resource"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_show, self).get_parser(prog_name)
        parser.add_argument('--name', '-n', default=os.environ.get('ENV_NAME'),
                            help='environment name')
        return parser

    def take_action(self, parsed_args):
        headers = ("VNC", "NODE-NAME")
        env = get_env(parsed_args.name)
        columns = [(node.get_vnc_port(),
                    node.name) for node in env.get_nodes()]
        return (headers, columns)


class do_erase(Command):
    "erase resource"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_erase, self).get_parser(prog_name)
        parser.add_argument('--name', '-n', default=os.environ.get('ENV_NAME'),
                            help='environment name')
        return parser

    def take_action(self, parsed_args):
        get_env(parsed_args.name).erase()


class do_start(Command):
    "start resource"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_start, self).get_parser(prog_name)
        parser.add_argument('--name', '-n', default=os.environ.get('ENV_NAME'),
                            help='environment name')
        return parser

    def take_action(self, parsed_args):
        get_env(parsed_args.name).start()


class do_destroy(Command):
    "destroy resource"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_destroy, self).get_parser(prog_name)
        parser.add_argument('--name', '-n', default=os.environ.get('ENV_NAME'),
                            help='environment name')
        return parser

    def take_action(self, parsed_args):
        get_env(parsed_args.name).destroy(verbose=False)


class do_suspend(Command):
    "suspend resource"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_suspend, self).get_parser(prog_name)
        parser.add_argument('--name', '-n', default=os.environ.get('ENV_NAME'),
                            help='environment name')
        return parser

    def take_action(self, parsed_args):
        get_env(parsed_args.name).suspend(verbose=False)


class do_resume(Command):
    "resume resource"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_resume, self).get_parser(prog_name)
        parser.add_argument('--name', '-n', default=os.environ.get('ENV_NAME'),
                            help='environment name')
        return parser

    def take_action(self, parsed_args):
        get_env(parsed_args.name).resume(verbose=False)


class do_revert(Command):
    "revert resource"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_revert, self).get_parser(prog_name)
        parser.add_argument('--name', '-n', default=os.environ.get('ENV_NAME'),
                            help='environment name')
        parser.add_argument('--snapshot-name', '-S',
                            default=os.environ.get('SNAPSHOT_NAME'),
                            help='snapshot name')
        return parser

    def take_action(self, parsed_args):
        get_env(parsed_args.name).revert(parsed_args.snapshot_name)


class do_snapshot(Command):
    "snapshot resource"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_snapshot, self).get_parser(prog_name)
        parser.add_argument('--name', '-n', default=os.environ.get('ENV_NAME'),
                            help='environment name')
        parser.add_argument('--snapshot-name', '-S',
                            default=os.environ.get('SNAPSHOT_NAME'),
                            help='snapshot name')
        return parser

    def take_action(self, parsed_args):
        get_env(parsed_args.name).snapshot(parsed_args.snapshot_name)


class do_synchronize(Command):
    "sync resources"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_synchronize, self).get_parser(prog_name)
        return parser

    def take_action(self, parsed_args):
        Environment.synchronize_all()


class do_snapshot_list(Lister):
    "snapshot list"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_snapshot_list, self).get_parser(prog_name)
        parser.add_argument('--name', '-n', default=os.environ.get('ENV_NAME'),
                            help='environment name')
        return parser

    def take_action(self, parsed_args):
        # self.log.info("parsed_args={}".format(parsed_args))
        snapshots = collections.OrderedDict()
        Snap = collections.namedtuple('Snap', ['info', 'nodes'])
        for node in get_env(parsed_args.name).get_nodes():
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
            columns.append((info.name,
                            info.created.strftime('%Y-%m-%d %H:%M:%S'),
                            ', '.join(nodes)))
        return (headers, columns)


class do_snapshot_delete(Command):
    "snapshot delete"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_snapshot_delete, self).get_parser(prog_name)
        parser.add_argument('--name', '-n', default=os.environ.get('ENV_NAME'),
                            help='environment name')
        parser.add_argument('--snapshot-name', '-S',
                            default=os.environ.get('SNAPSHOT_NAME'),
                            help='snapshot name')
        return parser

    def take_action(self, parsed_args):
        # self.log.info("parsed_args={}".format(parsed_args))
        for node in get_env(parsed_args.name).get_nodes():
            snaps = map(lambda x: x.name, node.get_snapshots())
            if parsed_args.snapshot_name in snaps:
                node.erase_snapshot(name=parsed_args.snapshot_name)


class do_net_list(Lister):
    "net list"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_net_list, self).get_parser(prog_name)
        parser.add_argument('--name', '-n', default=os.environ.get('ENV_NAME'),
                            help='environment name')
        return parser

    def take_action(self, parsed_args):
        # self.log.info("parsed_args={}".format(parsed_args))
        headers = ("NETWORK NAME", "IP NET")
        env = get_env(parsed_args.name)
        columns = [(net.name, net.ip_network) for net in env.get_networks()]
        return (headers, columns)


class do_timesync(Command):
    "time sync"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_timesync, self).get_parser(prog_name)
        parser.add_argument('--name', '-n',
                            default=os.environ.get('ENV_NAME'),
                            help='environment name')
        parser.add_argument('--node-name', '-N',
                            default=os.environ.get('NODE_NAME'),
                            help='node name')
        return parser

    def take_action(self, parsed_args):
        # self.log.info("parsed_args={}".format(parsed_args))
        env = get_env(parsed_args.name)
        if not parsed_args.node_name:
            nodes = [node.name for node in env.get_nodes()
                     if node.driver.node_active(node)]
        else:
            nodes = [parsed_args.node_name]

        cur_time = sync_time(env, nodes, skip_sync=True)
        for name in sorted(cur_time):
            self.log.info("Current time on \
                          '{0}' = {1}".format(name, cur_time[name]))
        self.log.info("Please wait for a few minutes\
                       while time is synchronized...")
        new_time = sync_time(env, nodes, skip_sync=False)
        for name in sorted(new_time):
            self.log.info("New time on \
                          '{0}' = {1}".format(name, new_time[name]))


class do_revert_resume(Command):
    "node revert-resume"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_revert_resume, self).get_parser(prog_name)
        parser.add_argument('--name', '-n',
                            default=os.environ.get('ENV_NAME'),
                            help='environment name')
        parser.add_argument('--snapshot-name', '-S',
                            default=os.environ.get('SNAPSHOT_NAME'),
                            help='snapshot name')
        parser.add_argument('--node-name', '-N',
                            default=os.environ.get('NODE_NAME'),
                            help='node name')
        parser.add_argument('--no-timesync', default=False,
                            action='store_true',
                            help='revert without timesync')
        return parser

    def take_action(self, parsed_args):
        # self.log.info("parsed_args={}".format(parsed_args))
        env = get_env(parsed_args.name)
        env.revert(parsed_args.snapshot_name, flag=False)
        env.resume(verbose=False)
        if not parsed_args.no_timesync:
            self.log.info('Time synchronization is starting')
            # do_timesync(name, node_name)
            env = get_env(parsed_args.name)
            if not parsed_args.node_name:
                nodes = [node.name for node in env.get_nodes()
                         if node.driver.node_active(node)]
            else:
                nodes = [parsed_args.node_name]
            cur_time = sync_time(env, nodes, skip_sync=True)
            for name in sorted(cur_time):
                self.log.info("Current time \
                               on '{0}' = {1}".format(name, cur_time[name]))
            self.log.info("Please wait for a few minutes\
                           while time is synchronized...")
            new_time = sync_time(env, nodes, skip_sync=False)
            for name in sorted(new_time):
                self.log.info("New time on \
                              '{0}' = {1}".format(name, new_time[name]))


class do_version(Command):
    "get version"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_version, self).get_parser(prog_name)
        return parser

    def take_action(self, parsed_args):
        import devops
        self.log.info(devops.__version__)
        # self.log.info("parsed_args={}".format(parsed_args))


class do_create(Command):
    "create"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_create, self).get_parser(prog_name)
        parser.add_argument('--name', '-n',
                            default=os.environ.get('ENV_NAME'),
                            help='environment name')
        parser.add_argument('--vcpu', default=1,
                            help='Set node VCPU count')
        parser.add_argument('--node-count', '-C', default=1,
                            help='How many nodes will be created')
        parser.add_argument('--ram', default=1024,
                            help='Set node RAM size')
        parser.add_argument('--net-pool', '-P', default='10.21.0.0/16:24',
                            help='Set ip network pool (cidr)')
        parser.add_argument('--iso-path', '-I',
                            help='Set Fuel ISO path')
        parser.add_argument('--admin-disk-size', default=50,
                            help='Set admin node disk size (GB)')
        parser.add_argument('--admin-ram', default=1536,
                            help='Select admin node RAM size (MB)')
        parser.add_argument('--admin-vcpu', default=2,
                            help='Select admin node VCPU count')
        parser.add_argument('--second-disk-size', default=50,
                            help='Allocate second disk for node with selected size(GB).\
                                  If set to 0, the disk will not be allocated')
        parser.add_argument('--third-disk-size', default=50,
                            help='Allocate third disk for node with selected size(GB).\
                                  If set to 0, the disk will not be allocated')
        return parser

    def take_action(self, parsed_args):
        # self.log.info("parsed_args={}".format(parsed_args))
        env_name = get_env(parsed_args.name).name
        for env in get_envs:
            if env.name == env_name:
                print("Please, set another environment name")
                raise SystemExit()
        env = Environment.create(env_name)
        networks, prefix = parsed_args.net_pool.split(':')
        Network.default_pool = Network.create_network_pool(
            networks=[ipaddr.IPNetwork(networks)], prefix=int(prefix))
        networks = Network.create_networks(environment=env)
        admin_node = admin_add(env,
                               parsed_args.admin_vcpu_count,
                               parsed_args.admin_ram_size,
                               parsed_args.iso_path,
                               networks)
        do_slave_add(parsed_args.name,
                     parsed_args.vcpu_count,
                     parsed_args.node_count,
                     parsed_args.ram_size,
                     parsed_args.second_disk_size,
                     parsed_args.third_disk_size,
                     force_define=False)
        env.define()
        a = admin_node.disk_devices.get(device='cdrom')
        a.volume.upload(parsed_args.iso_path)
        for net in env.get_networks():
            net.start()


class do_slave_add(Command):
    "slave add"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_slave_add, self).get_parser(prog_name)
        parser.add_argument('--name', '-n',
                            default=os.environ.get('ENV_NAME'),
                            help='environment name')
        parser.add_argument('--vcpu', default=1,
                            help='Set node VCPU count')
        parser.add_argument('--node-count', '-C', default=1,
                            help='How many nodes will be created')
        parser.add_argument('--ram', default=1024,
                            help='Set node RAM size')
        parser.add_argument('--second-disk-size', default=50,
                            help='Allocate second disk for node with selected size(GB).\
                                  If set to 0, the disk will not be allocated')
        parser.add_argument('--third-disk-size', default=50,
                            help='Allocate third disk for node with selected size(GB).\
                                  If set to 0, the disk will not be allocated')
        parser.add_argument('--force-define', default=True,
                            action='store_true',
                            help='force to define node')
        return parser

    def take_action(self, parsed_args):
        # self.log.info("parsed_args={}".format(parsed_args))
        env = get_env(parsed_args.name)
        created_nodes = len(env.get_nodes())
        for node in xrange(created_nodes,
                           created_nodes + parsed_args.node_count):
            node_name = "slave-%02d" % (node)
            node = env.add_node(name=node_name,
                                vcpu=parsed_args.vcpu,
                                memory=parsed_args.ram)
            disknames_capacity = {'system': 50 * 1024 ** 3}
            if parsed_args.second_disk_size > 0:
                a = parsed_args.second_disk_size * 1024 ** 3
                disknames_capacity['cinder'] = a
            if parsed_args.third_disk_size > 0:
                b = parsed_args.third_disk_size * 1024 ** 3
                disknames_capacity['swift'] = b
            node.attach_disks(disknames_capacity=disknames_capacity,
                              force_define=parsed_args.force_define)
            node.attach_to_networks()
            if parsed_args.force_define:
                node.define()


class do_slave_remove(Command):
    "do_slave_remove"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_slave_remove, self).get_parser(prog_name)
        parser.add_argument('--name', '-n',
                            default=os.environ.get('ENV_NAME'),
                            help='environment name')
        parser.add_argument('--node-name', '-N',
                            default=os.environ.get('NODE_NAME'),
                            help='node name')
        return parser

    def take_action(self, parsed_args):
        # self.log.info("parsed_args={}".format(parsed_args))
        env = get_env(parsed_args.name)
        volumes = []
        for drive in env.get_node(name=parsed_args.node_name).disk_devices:
            volumes.append(drive.volume)
        env.get_node(name=parsed_args.node_name).remove()
        for volume in volumes:
            volume.erase()


class do_slave_change(Command):
    "do_slave_change"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_slave_change, self).get_parser(prog_name)
        parser.add_argument('--name', '-n',
                            default=os.environ.get('ENV_NAME'),
                            help='environment name')
        parser.add_argument('--node-name', '-N',
                            default=os.environ.get('NODE_NAME'),
                            help='node name')
        parser.add_argument('--vcpu', default=1,
                            help='Set node VCPU count')
        parser.add_argument('--ram', default=1024,
                            help='Set node RAM size')
        return parser

    def take_action(self, parsed_args):
        # self.log.info("parsed_args={}".format(parsed_args))
        env = get_env(parsed_args.name)
        node = env.get_node(name=parsed_args.node_name)
        node.set_vcpu(vcpu=parsed_args.vcpu)
        node.set_memory(memory=parsed_args.ram)


class do_admin_setup(Command):
    "do_admin_setup"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_admin_setup, self).get_parser(prog_name)
        parser.add_argument('--name', '-n',
                            default=os.environ.get('ENV_NAME'),
                            help='environment name')
        parser.add_argument('--admin-disk-size', default=50,
                            help='Set admin node disk size (GB)')
        return parser

    def take_action(self, parsed_args):
        # self.log.info("parsed_args={}".format(parsed_args))
        env = get_env(parsed_args.name)
        admin_node = env.get_node(name='admin')
        admin_node.destroy()
        node_manager.admin_prepare_disks(node=admin_node,
                                         disk_size=parsed_args.admin_disk_size)
        admin_node.start()
        node_manager.admin_change_config(admin_node)
        admin_node.await("admin", timeout=10 * 60)
        node_manager.admin_wait_bootstrap(3000, env)


class do_admin_change(Command):
    "do_admin_change"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_admin_change, self).get_parser(prog_name)
        parser.add_argument('--name', '-n',
                            default=os.environ.get('ENV_NAME'),
                            help='environment name')
        parser.add_argument('--vcpu', default=2,
                            help='Set admin VCPU count')
        parser.add_argument('--ram', default=1536,
                            help='Set admin RAM size')
        return parser

    def take_action(self, parsed_args):
        # self.log.info("parsed_args={}".format(parsed_args))
        env = get_env(parsed_args.name)
        node = env.get_node(name="admin")
        node.set_vcpu(vcpu=parsed_args.vcpu)
        node.set_memory(memory=parsed_args.ram)


class do_admin_add(Command):
    "do_admin_add"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_admin_add, self).get_parser(prog_name)
        parser.add_argument('--name', '-n',
                            default=os.environ.get('ENV_NAME'),
                            help='environment name')
        parser.add_argument('--vcpu', default=2,
                            help='Set admin VCPU count')
        parser.add_argument('--ram', default=1536,
                            help='Set admin RAM size')
        parser.add_argument('--iso-path', '-I',
                            help='Set Fuel ISO path')
        return parser

    def take_action(self, parsed_args):
        # self.log.info("parsed_args={}".format(parsed_args))
        env = get_env(parsed_args.name)
        networks = Network.create_networks(environment=env)
        admin_add(env,
                  parsed_args.vcpu,
                  parsed_args.ram,
                  parsed_args.iso_path, networks)


class do_node_start(Command):
    "do_node_start"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_node_start, self).get_parser(prog_name)
        parser.add_argument('--name', '-n',
                            default=os.environ.get('ENV_NAME'),
                            help='environment name')
        parser.add_argument('--node-name', '-N',
                            default=os.environ.get('NODE_NAME'),
                            help='node name')
        return parser

    def take_action(self, parsed_args):
        # self.log.info("parsed_args={}".format(parsed_args))
        get_env(parsed_args.name).get_node(name=parsed_args.node_name).start()


class do_node_destroy(Command):
    "do_node_destroy"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_node_destroy, self).get_parser(prog_name)
        parser.add_argument('--name', '-n',
                            default=os.environ.get('ENV_NAME'),
                            help='environment name')
        parser.add_argument('--node-name', '-N',
                            default=os.environ.get('NODE_NAME'),
                            help='node name')
        return parser

    def take_action(self, parsed_args):
        # self.log.info("parsed_args={}".format(parsed_args))
        get_env(parsed_args.name).get_node(
            name=parsed_args.node_name).destroy()


class do_node_reset(Command):
    "do_node_reset"
    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(do_node_reset, self).get_parser(prog_name)
        parser.add_argument('--name', '-n',
                            default=os.environ.get('ENV_NAME'),
                            help='environment name')
        parser.add_argument('--node-name', '-N',
                            default=os.environ.get('NODE_NAME'),
                            help='node name')
        return parser

    def take_action(self, parsed_args):
        # self.log.info("parsed_args={}".format(parsed_args))
        get_env(parsed_args.name).get_node(
            name=parsed_args.node_name).reset()


def get_env(name):
    env = None
    try:
        env = Environment.get(name=name)
    except Environment.DoesNotExist:
        sys.exit("Enviroment with name {} doesn't exist.".format(name))
    return env


def get_envs():
    envs = None
    try:
        envs = Environment.list_all().values('name', 'created')
    except Environment.DoesNotExist:
        sys.exit("Enviroment doesn't exist.")
    return envs


def node_dict(node):
    return {'name': node.name,
            'vnc': node.get_vnc_port()}


def admin_add(env, admin_vcpu_count, admin_ram_size, iso_path, networks=None):
    if not (_get_file_size(iso_path)):
        print("Please, set correct ISO file")
        sys.exit(1)
    if networks is None:
        networks = []
        interfaces = settings.INTERFACE_ORDER
        for name in interfaces:
            networks.append(env.create_networks(name))
    return env.describe_admin_node(name="admin",
                                   vcpu=admin_vcpu_count,
                                   networks=networks,
                                   memory=admin_ram_size,
                                   iso_path=iso_path)


def main(argv=sys.argv[1:]):
    myapp = DevopsCli()
    return myapp.run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
