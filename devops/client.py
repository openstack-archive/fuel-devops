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

from keystoneauth1.identity import V2Password
from keystoneauth1.session import Session as KeystoneSession
import paramiko
# pylint: disable=redefined-builtin
from six.moves import xrange
# pylint: enable=redefined-builtin

from devops.error import DevopsError
from devops.helpers.helpers import wait_tcp
from devops.helpers.ntp import NtpGroup
from devops.helpers.ssh_client import SSHClient
from devops.helpers.templates import create_devops_config
from devops.helpers.templates import create_slave_config
from devops.helpers.templates import get_devops_config
from devops import logger
from devops.models.environment import Environment
from devops import settings


class DevopsClient(object):
    """TODO"""

    def __init__(self):
        self._env = None

    @property
    def env(self):
        return self._env

    def select_env(self, name):
        try:
            self._env = Environment.get(name=name)
        except Environment.DoesNotExist:
            self._env = None
            raise DevopsError("Enviroment with name {} doesn't exist."
                              "".format(name))

    @staticmethod
    def list_env_names():
        return [env.name for env in Environment.list_all()]

    @staticmethod
    def synchronize_all():
        Environment.synchronize_all()

    def create_env_from_config(self, config):
        """Creates env from template"""
        if isinstance(config, str):
            config = get_devops_config(config)

        # TODO(astudenov): move check for existing env to Environment.create
        env_name = config['template']['devops_settings']['env_name']
        for env in Environment.list_all():
            if env.name == env_name:
                raise DevopsError('Environment {!r} - already exists.\n'
                                  'Please, set another environment name.'
                                  ''.format(env_name))

        self._env = Environment.create_environment(config)
        self._env.define()

        # Start all l2 network devices
        for group in self._env.get_groups():
            for net in group.get_l2_network_devices():
                net.start()

        return self._env

    def create_env(self,
                   boot_from='cdrom',
                   env_name=None,
                   admin_iso_path=None,
                   admin_vcpu=None,
                   admin_memory=None,
                   admin_sysvolume_capacity=None,
                   nodes_count=None,
                   slave_vcpu=None,
                   slave_memory=None,
                   second_volume_capacity=None,
                   third_volume_capacity=None,
                   net_pool=None,
                   ):
        """Backward compatibility for fuel-qa

        Creates env from list of environment variables
        """
        if net_pool:
            net_pool = net_pool.split(':')

        hw = settings.HARDWARE

        config = create_devops_config(
            boot_from=boot_from,
            env_name=env_name or settings.ENV_NAME,
            admin_vcpu=admin_vcpu or hw['admin_node_cpu'],
            admin_memory=admin_memory or hw['admin_node_memory'],
            admin_sysvolume_capacity=(
                admin_sysvolume_capacity or settings.ADMIN_NODE_VOLUME_SIZE),
            admin_iso_path=admin_iso_path or settings.ISO_PATH,
            nodes_count=nodes_count,
            numa_nodes=hw['numa_nodes'],
            slave_vcpu=slave_vcpu or hw['slave_node_cpu'],
            slave_memory=slave_memory or hw["slave_node_memory"],
            slave_volume_capacity=settings.NODE_VOLUME_SIZE,
            second_volume_capacity=(
                second_volume_capacity or settings.NODE_VOLUME_SIZE),
            third_volume_capacity=(
                third_volume_capacity or settings.NODE_VOLUME_SIZE),
            use_all_disks=settings.USE_ALL_DISKS,
            ironic_nodes_count=settings.IRONIC_NODES_COUNT,
            networks_bonding=settings.BONDING,
            networks_bondinginterfaces=settings.BONDING_INTERFACES,
            networks_multiplenetworks=settings.MULTIPLE_NETWORKS,
            networks_nodegroups=settings.NODEGROUPS,
            networks_interfaceorder=settings.INTERFACE_ORDER,
            networks_pools=dict(
                admin=net_pool or settings.POOLS['admin'],
                public=net_pool or settings.POOLS['public'],
                management=net_pool or settings.POOLS['management'],
                private=net_pool or settings.POOLS['private'],
                storage=net_pool or settings.POOLS['storage'],
            ),
            networks_forwarding=settings.FORWARDING,
            networks_dhcp=settings.DHCP,
            driver_enable_acpi=settings.DRIVER_PARAMETERS['enable_acpi'],
        )
        return self.create_env_from_config(config)

    def add_slaves(self,
                   nodes_count,
                   slave_vcpu=1,
                   slave_memory=1024,
                   second_volume_capacity=50,
                   third_volume_capacity=50,
                   force_define=True):
        group = self._env.get_group(name='default')
        created_nodes = len(group.get_nodes())

        new_nodes = []
        for node_num in xrange(created_nodes, created_nodes + nodes_count):
            node_name = "slave-{:02d}".format(node_num)
            slave_conf = create_slave_config(
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
        raise DevopsError('Environment {!r} has no admin node'
                          ''.format(self._env.name))

    def get_admin_ip(self):
        return self.get_admin().get_ip_address_by_network_name(
            settings.SSH_CREDENTIALS['admin_network'])

    def get_admin_remote(self, login=settings.SSH_CREDENTIALS['login'],
                         password=settings.SSH_CREDENTIALS['password']):
        admin_ip = self.get_admin_ip()
        admin_node = self.get_admin()
        wait_tcp(host=admin_ip, port=admin_node.ssh_port, timeout=180,
                 timeout_msg=("Admin node {ip} is not accessible by SSH."
                              "".format(ip=admin_ip)))
        return SSHClient(admin_ip, username=login, password=password)

    def get_private_keys(self):
        ssh_keys = []
        admin_remote = self.get_admin_remote()
        for key_string in ['/root/.ssh/id_rsa',
                           '/root/.ssh/bootstrap.rsa']:
            if admin_remote.isfile(key_string):
                with admin_remote.open(key_string) as f:
                    ssh_keys.append(paramiko.RSAKey.from_private_key(f))
        return ssh_keys

    def get_node_ip(self, node_name):
        node = self._env.get_node(name=node_name)
        node_mac = node.interfaces[0].mac_address

        nailgun_client = NailgunClient(ip=self.get_admin_ip())
        ip = nailgun_client.get_slave_ip_by_mac(node_mac)
        return ip

    def get_node_remote(self, node_name,
                        login=settings.SSH_SLAVE_CREDENTIALS['login'],
                        password=settings.SSH_SLAVE_CREDENTIALS['password']):
        node = self._env.get_node(name=node_name)
        ip = self.get_node_ip(node_name)
        wait_tcp(
            host=ip, port=node.ssh_port, timeout=180,
            timeout_msg="Node {ip} is not accessible by SSH.".format(ip=ip))
        return SSHClient(ip, username=login, password=password,
                         private_keys=self.get_private_keys())

    def timesync(self, node_names=None, skip_sync=False):
        """Synchronize time on nodes

           param: node_names - list of devops node names
           param: skip_sync - only get the current time without sync
           return: dict{node_name: node_time, ...}
        """
        if node_names is None:
            node_names = [node.name for node in self.get_active_nodes()]

        admin_ip = self.get_admin_ip()

        group = NtpGroup()
        for node_name in node_names:
            if node_name == 'admin':
                remote = self.get_admin_remote()
            else:
                remote = self.get_node_remote(node_name=node_name)

            group.add_node(remote, node_name, admin_ip)

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
        return self.timesync(node_names=node_names, skip_sync=True)


class NailgunClient(object):

    def __init__(self, ip):
        self.ip = ip

    def get_slave_ip_by_mac(self, mac):
        js = self.get_nodes_json()

        def poor_mac(mac_addr):
            return [m.lower() for m in mac_addr
                    if m.lower() in '01234546789abcdef']

        for node in js:
            for interface in node['meta']['interfaces']:
                if poor_mac(interface['mac']) == poor_mac(mac):
                    logger.debug("For mac {0} found ip {1}"
                                 .format(mac, node['ip']))
                    return node['ip']
        raise DevopsError('There is no match between MAC {0}'
                          ' and Nailgun MACs'.format(mac))

    def get_nodes_json(self):
        keystone_auth = V2Password(
            auth_url="http://{}:5000/v2.0".format(self.ip),
            username=settings.KEYSTONE_CREDS['username'],
            password=settings.KEYSTONE_CREDS['password'],
            tenant_name=settings.KEYSTONE_CREDS['tenant_name'])
        keystone_session = KeystoneSession(auth=keystone_auth, verify=False)
        nodes = keystone_session.get(
            '/nodes',
            endpoint_filter={'service_type': 'fuel'}
        )
        return nodes.json()
