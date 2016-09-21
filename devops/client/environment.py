#    Copyright 2016 Mirantis, Inc.
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

import paramiko
# pylint: disable=redefined-builtin
# noinspection PyUnresolvedReferences
from six.moves import xrange
# pylint: enable=redefined-builtin

from devops.client import nailgun
from devops import error
from devops.helpers import helpers
from devops.helpers import ntp
from devops.helpers import ssh_client
from devops.helpers import templates
from devops import settings


class DevopsEnvironment(object):
    """DevopsEnvironment

    Contains all methods to controll environment and nodes
    """

    def __init__(self, env):
        self._env = env

    def __getattr__(self, name):
        return getattr(self._env, name)

    def add_slaves(self,
                   nodes_count,
                   slave_vcpu=1,
                   slave_memory=1024,
                   second_volume_capacity=50,
                   third_volume_capacity=50,
                   force_define=True,
                   group_name='default',
                   ):
        group = self._env.get_group(name=group_name)

        created_nodes = len(group.get_nodes())

        new_nodes = []
        for node_num in xrange(created_nodes, created_nodes + nodes_count):
            node_name = "slave-{:02d}".format(node_num)
            slave_conf = templates.create_slave_config(
                slave_name=node_name,
                slave_role='fuel_slave',
                slave_vcpu=slave_vcpu,
                slave_memory=slave_memory,
                slave_volume_capacity=settings.NODE_VOLUME_SIZE,
                second_volume_capacity=second_volume_capacity,
                third_volume_capacity=third_volume_capacity,
                interfaceorder=settings.INTERFACE_ORDER,
                numa_nodes=settings.HARDWARE['numa_nodes'],
                use_all_disks=True,
                networks_multiplenetworks=settings.MULTIPLE_NETWORKS,
                networks_nodegroups=settings.NODEGROUPS,
                networks_bonding=settings.BONDING,
                networks_bondinginterfaces=settings.BONDING_INTERFACES,
            )
            node = group.add_node(**slave_conf)
            if force_define is True:
                for volume in node.get_volumes():
                    volume.define()
                node.define()

            new_nodes.append(node)

        return new_nodes

    def get_default_gw(self, l2_network_device_name='admin'):
        l2_net_dev = self._env.get_env_l2_network_device(
            name=l2_network_device_name)
        return l2_net_dev.address_pool.gateway

    def has_admin(self):
        return self._env.get_nodes(name='admin').exists()

    def admin_setup(self, boot_from='cdrom', iface='enp0s3',
                    wait_for_external_config='no'):
        admin_node = self.get_admin()
        if admin_node.kernel_cmd is None:
            admin_node.kernel_cmd = admin_node.ext.get_kernel_cmd(
                boot_from=boot_from,
                wait_for_external_config=wait_for_external_config,
                iface=iface)
        admin_node.ext.bootstrap_and_wait()
        admin_node.ext.deploy_wait()

        return admin_node

    def get_active_nodes(self):
        return [node for node in self._env.get_nodes() if node.is_active()]

    def get_admin(self):
        if self.has_admin():
            return self._env.get_node(name='admin')
        raise error.DevopsError(
            'Environment {!r} has no admin node'.format(self._env.name))

    @staticmethod
    def get_admin_login():
        return settings.SSH_CREDENTIALS['login']

    def get_admin_ip(self):
        return self.get_admin().get_ip_address_by_network_name(
            settings.SSH_CREDENTIALS['admin_network'])

    def get_admin_remote(self, login=settings.SSH_CREDENTIALS['login'],
                         password=settings.SSH_CREDENTIALS['password']):
        admin_ip = self.get_admin_ip()
        admin_node = self.get_admin()
        helpers.wait_tcp(
            host=admin_ip, port=admin_node.ssh_port, timeout=180,
            timeout_msg=("Admin node {ip} is not accessible by SSH."
                         "".format(ip=admin_ip)))
        return ssh_client.SSHClient(
            admin_ip,
            auth=ssh_client.SSHAuth(username=login, password=password))

    def get_private_keys(self):
        ssh_keys = []
        with self.get_admin_remote() as admin_remote:
            for key_string in ['/root/.ssh/id_rsa',
                               '/root/.ssh/bootstrap.rsa']:
                if admin_remote.isfile(key_string):
                    with admin_remote.open(key_string) as f:
                        ssh_keys.append(paramiko.RSAKey.from_private_key(f))
        return ssh_keys

    def get_node_ip(self, node_name):
        node = self.get_node(name=node_name)
        node_mac = node.interfaces[0].mac_address

        nailgun_client = nailgun.NailgunClient(ip=self.get_admin_ip())
        ip = nailgun_client.get_slave_ip_by_mac(node_mac)
        return ip

    def get_node_remote(self, node_name,
                        login=settings.SSH_SLAVE_CREDENTIALS['login'],
                        password=settings.SSH_SLAVE_CREDENTIALS['password']):
        node = self.get_node(name=node_name)
        ip = self.get_node_ip(node_name)
        helpers.wait_tcp(
            host=ip, port=node.ssh_port, timeout=180,
            timeout_msg="Node {ip} is not accessible by SSH.".format(ip=ip))
        return ssh_client.SSHClient(
            ip,
            auth=ssh_client.SSHAuth(
                username=login,
                password=password,
                keys=self.get_private_keys()))

    def sync_time(self, node_names=None, skip_sync=False):
        """Synchronize time on nodes

           param: node_names - list of devops node names
           param: skip_sync - only get the current time without sync
           return: dict{node_name: node_time, ...}
        """
        if node_names is None:
            node_names = [node.name for node in self.get_active_nodes()]

        group = ntp.GroupNtpSync()
        for node_name in node_names:
            if node_name == 'admin':
                remote = self.get_admin_remote()
            else:
                remote = self.get_node_remote(node_name=node_name)

            group.add_node(remote, node_name)

        with group:
            if not skip_sync:
                group.sync_time('admin')
                group.sync_time('pacemaker')
                group.sync_time('other')
            return group.get_curr_time()

    def get_curr_time(self, node_names=None):
        """Get current time on nodes

           param: node_names - list of devops node names
           return: dict{node_name: node_time, ...}
        """
        return self.sync_time(node_names=node_names, skip_sync=True)
