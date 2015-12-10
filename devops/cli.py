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
import os
import sys

import ipaddr
import tabulate
import click


from devops.helpers.helpers import _get_file_size
from devops.helpers import node_manager
from devops.helpers.ntp import sync_time
from devops.models import Environment
from devops.models.network import Network
from devops import settings


class AliasedGroup(click.Group):

    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [x for x in self.list_commands(ctx)
                   if x[3:].startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))


@click.command(cls=AliasedGroup)
def cli():
    print("{} {}".format(sys._getframe().f_code.co_name, locals()))


@cli.command('list')
@click.option('--ips', 'list_ips',
              default=False, is_flag=True,
              help='show admin node ip addresses')
@click.option('--timestamps', 'timestamps',
              default=False, is_flag=True,
              help='show creation timestamps')
def do_list(list_ips, timestamps):
    env_list = get_envs()
    columns = []
    for env in env_list:
        column = collections.OrderedDict({'NAME': env['name']})
        if list_ips:
            cur_env = get_env(env.get('name'))
            admin_ip = ''
            if 'admin' in [node.name for node in cur_env.get_nodes()]:
                admin_ip = (cur_env.get_node(name='admin').
                            get_ip_address_by_network_name('admin'))
            column['ADMIN IP'] = admin_ip
        if timestamps:
            column['CREATED'] = env['created'].strftime('%Y-%m-%d_%H:%M:%S')
        columns.append(column)
    print_table(headers="keys", columns=columns)
    # print("{} {}".format(sys._getframe().f_code.co_name, locals()))


@cli.command('show')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
def do_show(name):
    headers = ("VNC", "NODE-NAME")
    env = get_env(name)
    columns = [(node.get_vnc_port(), node.name) for node in env.get_nodes()]
    print_table(headers=headers, columns=columns)
    # print("{} {}".format(sys._getframe().f_code.co_name, locals()))


@cli.command('erase')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
def do_erase(name):
    print("{} {}".format(sys._getframe().f_code.co_name, locals()))
    get_env(name).erase()


@cli.command('start')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
def do_start(name):
    get_env(name).start()


@cli.command('destroy')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
def do_destroy(name):
    get_env(name).suspend(verbose=False)


@cli.command('suspend')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
def do_suspend(name):
    get_env(name).suspend(verbose=False)


@cli.command('resume')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
def do_resume(name):
    get_env(name).resume(verbose=False)


@cli.command('revert')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
@click.option('-S', '--snapshot-name', 'snapshot_name',
              default=os.environ.get('SNAPSHOT_NAME'),
              help='snapshot name', envvar='SNAPSHOT_NAME')
def do_revert(name, snapshot_name):
    get_env(name).revert(snapshot_name, flag=False)


@cli.command('snapshot')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
@click.option('-S', '--snapshot-name', 'snapshot_name',
              default=os.environ.get('SNAPSHOT_NAME'),
              help='snapshot name', envvar='SNAPSHOT_NAME')
def do_snapshot(name, snapshot_name):
    get_env(name).snapshot(snapshot_name)


@cli.command('sync')
def do_synchronize():
    Environment.synchronize_all()


@cli.command('snapshot-list')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
def do_snapshot_list(name):
    snapshots = collections.OrderedDict()
    Snap = collections.namedtuple('Snap', ['info', 'nodes'])

    for node in get_env(name).get_nodes():
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

    print_table(columns=columns, headers=headers)


@cli.command('snapshot-delete')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
@click.option('-S', '--snapshot-name', 'snapshot_name',
              default=os.environ.get('SNAPSHOT_NAME'),
              help='snapshot name', envvar='SNAPSHOT_NAME')
def do_snapshot_delete(name, snapshot_name):
    for node in get_env(name).get_nodes():
        snaps = map(lambda x: x.name, node.get_snapshots())
        if snapshot_name in snaps:
            node.erase_snapshot(name=snapshot_name)


@cli.command('net-list')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
def do_net_list(name):
    headers = ("NETWORK NAME", "IP NET")
    env = get_env(name)
    columns = [(net.name, net.ip_network) for net in env.get_networks()]
    print_table(headers=headers, columns=columns)


@cli.command('time-sync')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
@click.option('-N', '--node-name', 'node_name',
              default=os.environ.get('NODE_NAME'),
              help='node name', envvar='NODE_NAME')
def do_timesync(name, node_name):
    env = get_env(name)
    if not node_name:
        nodes = [node.name for node in env.get_nodes()
                 if node.driver.node_active(node)]
    else:
        nodes = [node_name]

    cur_time = sync_time(env, nodes, skip_sync=True)
    for name in sorted(cur_time):
        print("Current time on '{0}' = {1}".format(name, cur_time[name]))

    print("Please wait for a few minutes while time is synchronized...")

    new_time = sync_time(env, nodes, skip_sync=False)
    for name in sorted(new_time):
        print("New time on '{0}' = {1}".format(name, new_time[name]))


@cli.command('revert-resume')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
@click.option('-S', '--snapshot-name', 'snapshot_name',
              default=os.environ.get('SNAPSHOT_NAME'),
              help='snapshot name', envvar='SNAPSHOT_NAME')
@click.option('-N', '--node-name', 'node_name',
              default=os.environ.get('NODE_NAME'),
              help='node name', envvar='NODE_NAME')
@click.option('--no-timesync', 'no_timesync',
              default=False, is_flag=True,
              help='revert without timesync')
def do_revert_resume(name, snapshot_name, node_name, no_timesync):
    env = get_env(name)
    env.revert(snapshot_name, flag=False)
    env.resume(verbose=False)
    if not no_timesync:
        print('Time synchronization is starting')
        do_timesync(name, node_name)


@cli.command('version')
def do_version():
    import devops
    print(devops.__version__)


@cli.command('create')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
@click.option('--vcpu', 'vcpu_count',
              help='Set node VCPU count',
              default=1)
@click.option('-C', '--node-count', 'node_count',
              help='How many nodes will be created',
              default=1)
@click.option('--ram', 'ram_size',
              help='Set node RAM size',
              default=1024)
@click.option('-P', '--net-pool', 'net_pool',
              help='Set ip network pool (cidr)',
              default="10.21.0.0/16:24")
@click.option('-I', '--iso-path', 'iso_path',
              help='Set Fuel ISO path', nargs=1,
              type=click.Path(exists=True))
@click.option('--admin-disk-size', 'admin_disk_size',
              help='Set admin node disk size (GB)',
              default=50)
@click.option('--admin-ram', 'admin_ram_size',
              help='Select admin node RAM size (MB)',
              default=1536)
@click.option('--admin-vcpu', 'admin_vcpu_count',
              help='Select admin node VCPU count',
              default=2)
@click.option('--second-disk-size', 'second_disk_size',
              help='Allocate second disk for node with selected size(GB).\
                    If set to 0, the disk will not be allocated',
              default=50)
@click.option('--third-disk-size', 'third_disk_size',
              help='Allocate third disk for node with selected size(GB).\
                    If set to 0, the disk will not be allocated',
              default=50)
def do_create(name, vcpu_count, node_count, ram_size, net_pool,
              iso_path, admin_disk_size, admin_ram_size,
              admin_vcpu_count, second_disk_size, third_disk_size):
    env_name = get_env(name).name
    for env in get_envs:
        if env.name == env_name:
            print("Please, set another environment name")
            raise SystemExit()
    env = Environment.create(env_name)
    networks, prefix = net_pool.split(':')
    Network.default_pool = Network.create_network_pool(
        networks=[ipaddr.IPNetwork(networks)], prefix=int(prefix))
    networks = Network.create_networks(environment=env)
    admin_node = admin_add(env, admin_vcpu_count, admin_ram_size,
                           iso_path, networks)
    do_slave_add(name, vcpu_count, node_count, ram_size, second_disk_size,
                 third_disk_size, force_define=False)
    env.define()
    admin_node.disk_devices.get(device='cdrom').volume.upload(iso_path)
    for net in env.get_networks():
        net.start()


@cli.command('slave-add')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
@click.option('--vcpu', 'vcpu_count',
              help='Set node VCPU count',
              default=1)
@click.option('-C', '--node-count', 'node_count',
              help='How many nodes will be created',
              default=1)
@click.option('--ram', 'ram_size',
              help='Set node RAM size',
              default=1024)
@click.option('--second-disk-size', 'second_disk_size',
              help='Allocate second disk for node with selected size(GB).\
                    If set to 0, the disk will not be allocated',
              default=50)
@click.option('--third-disk-size', 'third_disk_size',
              help='Allocate third disk for node with selected size(GB).\
                    If set to 0, the disk will not be allocated',
              default=50)
@click.option('--force-define', 'force_define',
              default=True, is_flag=True,
              help='force to define node')
def do_slave_add(name, vcpu_count, node_count, ram_size, second_disk_size,
                 third_disk_size, force_define=True):
    env = get_env(name)
    created_nodes = len(env.get_nodes())
    for node in xrange(created_nodes, created_nodes + node_count):
        node_name = "slave-%02d" % (node)
        node = env.add_node(name=node_name, vcpu=vcpu_count, memory=ram_size)
        disknames_capacity = {'system': 50 * 1024 ** 3}
        if second_disk_size > 0:
            disknames_capacity['cinder'] = second_disk_size * 1024 ** 3
        if third_disk_size > 0:
            disknames_capacity['swift'] = third_disk_size * 1024 ** 3
        node.attach_disks(disknames_capacity=disknames_capacity,
                          force_define=force_define)
        node.attach_to_networks()
        if force_define:
            node.define()


@cli.command('slave-remove')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
@click.option('-N', '--node-name', 'node_name',
              default=os.environ.get('NODE_NAME'),
              help='node name', envvar='NODE_NAME')
def do_slave_remove(name, node_name):
    env = get_env(name)
    volumes = []
    for drive in env.get_node(name=node_name).disk_devices:
        volumes.append(drive.volume)
    env.get_node(name=node_name).remove()
    for volume in volumes:
        volume.erase()


@cli.command('slave-change')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
@click.option('--vcpu', 'vcpu_count',
              help='Set node VCPU count',
              default=1)
@click.option('--ram', 'ram_size',
              help='Set node RAM size',
              default=1024)
@click.option('-N', '--node-name', 'node_name',
              default=os.environ.get('NODE_NAME'),
              help='node name', envvar='NODE_NAME')
def do_slave_change(name, vcpu_count, ram_size, node_name):
    env = get_env(name)
    node = env.get_node(name=node_name)
    node.set_vcpu(vcpu=vcpu_count)
    node.set_memory(memory=ram_size)


@cli.command('admin-setup')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
@click.option('--admin-disk-size', 'admin_disk_size',
              help='Set admin node disk size (GB)',
              default=50)
def do_admin_setup(name, admin_disk_size):
    env = get_env(name)
    admin_node = env.get_node(name='admin')
    admin_node.destroy()
    node_manager.admin_prepare_disks(node=admin_node,
                                     disk_size=admin_disk_size)
    admin_node.start()
    node_manager.admin_change_config(admin_node)
    admin_node.await("admin", timeout=10 * 60)
    node_manager.admin_wait_bootstrap(3000, env)


@cli.command('admin-change')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
@click.option('--admin-ram', 'admin_ram_size',
              help='Select admin node RAM size (MB)',
              default=1536)
@click.option('--admin-vcpu', 'admin_vcpu_count',
              help='Select admin node VCPU count',
              default=2)
def do_admin_change(name, admin_ram_size, admin_vcpu_count):
    env = get_env(name)
    node = env.get_node(name="admin")
    node.set_vcpu(vcpu=admin_vcpu_count)
    node.set_memory(memory=admin_ram_size)


@cli.command('admin-add')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
@click.option('--admin-ram', 'admin_ram_size',
              help='Select admin node RAM size (MB)',
              default=1536)
@click.option('--admin-vcpu', 'admin_vcpu_count',
              help='Select admin node VCPU count',
              default=2)
@click.option('-I', '--iso-path', 'iso_path',
              help='Set Fuel ISO path', nargs=1,
              type=click.Path(exists=True))
def do_admin_add(name, admin_ram_size, admin_vcpu_count, iso_path):
    env = get_env(name)
    networks = Network.create_networks(environment=env)
    admin_add(env, admin_vcpu_count, admin_ram_size, iso_path, networks)


@cli.command('node-start')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
@click.option('-N', '--node-name', 'node_name',
              default=os.environ.get('NODE_NAME'),
              help='node name', envvar='NODE_NAME')
def do_node_start(name, node_name):
    get_env(name).get_node(name=node_name).start()


@cli.command('node-destroy')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
@click.option('-N', '--node-name', 'node_name',
              default=os.environ.get('NODE_NAME'),
              help='node name', envvar='NODE_NAME')
def do_node_destroy(name, node_name):
    get_env(name).get_node(name=node_name).destroy()


@cli.command('node-reset')
@click.option('-n', '--name', 'name',
              default=os.environ.get('ENV_NAME'),
              help='environment name', envvar='ENV_NAME')
@click.option('-N', '--node-name', 'node_name',
              default=os.environ.get('NODE_NAME'),
              help='node name', envvar='NODE_NAME')
def do_node_reset(name, node_name):
    get_env(name).get_node(name=node_name).reset()


# additional module functions below
def print_table(headers, columns):
    print(tabulate.tabulate(columns, headers=headers,
          tablefmt="simple"))


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

if __name__ == '__main__':
    cli()
