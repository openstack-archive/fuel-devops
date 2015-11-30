#    Copyright 2013 - 2015 Mirantis, Inc.
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

import time

from django.conf import settings
from django.db import models
from ipaddr import IPNetwork
from paramiko import Agent
from paramiko import RSAKey

from devops.helpers.helpers import _get_file_size
from devops.helpers.helpers import SSHClient
from devops.helpers.templates import create_devops_config
from devops.helpers.templates import get_devops_config
from devops import logger
from devops.models.base import BaseModel
from devops.models.network import Address_Pool
from devops.models.network import Interface
# from devops.models.network import Network
from devops.models.node import Node
from devops.models.volume import Volume
from devops.models.volume import DiskDevice
from devops.models.driver import Driver
from devops.models.group import Group


class Environment(BaseModel):
    class Meta(object):
        db_table = 'devops_environment'
        app_label = 'devops'

    name = models.CharField(max_length=255, unique=True, null=False)

    hostname = 'nailgun'
    domain = 'test.domain.local'
    nat_interface = ''  # INTERFACES.get('admin')
    # TODO(akostrikov) As we providing admin net names in fuel-qa/settings,
    # we should create constant and use it in fuel-qa or
    # pass admin net names to Environment from fuel-qa.
    admin_net = 'admin'
    admin_net2 = 'admin2'
    os_image = None  # Dirty hack. Check for os_image attribute for relevancy.


# OLD
#==============================================
# LEGACY, TO CHECK IN fuel-qa
    def get_volume(self, *args, **kwargs):
        return self.volume_set.get(*args, **kwargs)

# LEGACY, TO CHECK IN fuel-qa
    def get_volumes(self, *args, **kwargs):
        return self.volume_set.filter(*args, **kwargs)

# LEGACY, TO CHECK IN fuel-qa
    def get_network(self, *args, **kwargs):
#        return self.network_set.get(*args, **kwargs)
        return self.l2_network_device_set.get(*args, **kwargs)

# LEGACY, TO CHECK IN fuel-qa
    def get_networks(self, *args, **kwargs):
#        return self.network_set.filter(*args, **kwargs)
        return self.l2_network_device_set.filter(*args, **kwargs)


    def add_node(self, memory, name, vcpu=1, boot=None, role='slave'):
        return Node.node_create(
            name=name,
            memory=memory,
            vcpu=vcpu,
            environment=self,
            role=role,
            boot=boot)

    def add_empty_volume(self, node, name, capacity,
                         device='disk', bus='virtio', format='qcow2'):
        return DiskDevice.node_attach_volume(
            node=node,
            volume=Volume.volume_create(
                name=name,
                capacity=capacity,
                environment=self,
                format=format),
            device=device,
            bus=bus)
#======================================

# NEW
    def get_allocated_networks(self):
        allocated_networks = []
        for group in self.get_groups():
            allocated_networks += group.get_allocated_networks()
        return allocated_networks

# NEW
    def get_address_pool(self, *args, **kwargs):
        return self.address_pool_set.get(*args, **kwargs)

# NEW    
    def get_address_pools(self, *args, **kwargs):
        return self.address_pool_set.filter(*args, **kwargs)

# NEW
    def get_group(self, *args, **kwargs):
        return self.group_set.get(*args, **kwargs)

# NEW
    def get_groups(self, *args, **kwargs):
        return self.group_set.filter(*args, **kwargs)

#    def get_node(self, *args, **kwargs):
#        return self.node_set.get(*args, **kwargs)
    def get_node(self, *args, **kwargs):
        return Node.objects.get(*args, group__environment=self, **kwargs)

#    def get_nodes(self, *args, **kwargs):
#        return self.node_set.filter(*args, **kwargs)
    def get_nodes(self, *args, **kwargs):
        return Node.objects.filter(*args, group__environment=self, **kwargs)

# NEW
    def add_groups(self, groups):
        for group_data in groups:
            driver_data = group_data['driver']
            self.add_group(
                group_name=group_data['name'],
                driver_name=driver_data['name'],
                **driver_data.get('params', {})
            )

# NEW
    def add_group(self, group_name, driver_name, **driver_params):
        driver = Driver.driver_create(
            name=driver_name,
            **driver_params
        )
        return Group.group_create(
            name=group_name,
            environment=self,
            driver=driver,
        )

# NEW    
    def add_address_pools(self, address_pools):
        for name, data in address_pools.items():
            self.add_address_pool(
                name=name,
                net=data['net'],
                **data.get('params', {})
            )

# NEW
    def add_address_pool(self, name, net, **params):
        Address_Pool.address_pool_create(
            environment=self,
            name=name,
            net=net,
            **params
        )



# OLD
    @classmethod
    def create(cls, name):
        """Create Environment instance with given name.

        :rtype: devops.models.Environment
        """
        return cls.objects.create(name=name)

# OLD
    @classmethod
    def get(cls, *args, **kwargs):
        return cls.objects.get(*args, **kwargs)

# OLD
    @classmethod
    def list_all(cls):
        return cls.objects.all()

# ??? OLD
    def has_snapshot(self, name):
        if self.get_nodes():
            return all(n.has_snapshot(name) for n in self.get_nodes())
        else:
            return False

#    def define(self, skip=True):
#        # 'skip' param is a temporary workaround.
#        # It will be removed with introducing the new database schema
#        # See the task QA-239 for details.
#        if not skip:
#            for network in self.get_networks():
#                network.define()
#            for volume in self.get_volumes():
#                volume.define()
#            for node in self.get_nodes():
#                node.define()
    def define(self):
        for group in self.get_groups():
            group.define()



#    def start(self, nodes=None):
#        for network in self.get_networks():
#            network.start()
#        for node in nodes or self.get_nodes():
#            node.start()
    def start(self, nodes=None):
        for group in self.get_groups():
            group.start(nodes)


#    def destroy(self, verbose=False):
#        for node in self.get_nodes():
#            node.destroy(verbose=verbose)
    def destroy(self):
        for group in self.get_groups():
            group.destroy()

#    def erase(self):
#        for node in self.get_nodes():
#            node.erase()
#        for network in self.get_networks():
#            network.erase()
#        for volume in self.get_volumes():
#            volume.erase()
#        self.delete()
    def erase(self):
        for group in self.get_groups():
            group.erase()
        self.delete()


# OLD - TO MODIFY BY GROUPS
#===============================================================
    @classmethod
    def erase_empty(cls):
        for env in cls.list_all():
            if env.get_nodes().count() == 0:
                env.erase()

    def suspend(self, verbose=False):
        for node in self.get_nodes():
            node.suspend(verbose)

    def resume(self, verbose=False):
        for node in self.get_nodes():
            node.resume(verbose)

    def snapshot(self, name=None, description=None, force=False):
        if name is None:
            name = str(int(time.time()))
        for node in self.get_nodes():
            node.snapshot(name=name, description=description, force=force)

    def revert(self, name=None, destroy=True, flag=True):
        if destroy:
            for node in self.get_nodes():
                node.destroy(verbose=False)
        if flag and not self.has_snapshot(name):
            raise Exception("some nodes miss snapshot,"
                            " test should be interrupted")
        for node in self.get_nodes():
            node.revert(name, destroy=False)

    @classmethod
    def synchronize_all(cls):
        driver = cls.get_driver()
        nodes = {driver._get_name(e.name, n.name): n
                 for e in cls.list_all()
                 for n in e.get_nodes()}
        domains = set(driver.node_list())

        # FIXME (AWoodward) This willy nilly wacks domains when you run this
        #  on domains that are outside the scope of devops, if anything this
        #  should cause domains to be imported into db instead of undefined.
        #  It also leaves network and volumes around too
        #  Disabled until a safer implementation arrives

        # Undefine domains without devops nodes
        #
        # domains_to_undefine = domains - set(nodes.keys())
        # for d in domains_to_undefine:
        #    driver.node_undefine_by_name(d)

        # Remove devops nodes without domains
        nodes_to_remove = set(nodes.keys()) - domains
        for n in nodes_to_remove:
            nodes[n].delete()
        cls.erase_empty()

        logger.info('Undefined domains: %s, removed nodes: %s' %
                    (0, len(nodes_to_remove)))

    def create_networks(self, name, l2_device_config, address_pools):

        # TODO(ddmitriev): use 'address_pool' attribute to get the address_pool
        # for 'l2_device' as an object

        # Get address_pool from 'address_pools' object
        if 'address_pool' in l2_device_config:
            address_pool = address_pools[l2_device_config['address_pool']]

            networks, prefix = address_pool['net'].split(':')
            ip_networks = [IPNetwork(x) for x in networks.split(',')]
            new_prefix = int(prefix)
            pool = Network.create_network_pool(networks=ip_networks,
                                               prefix=new_prefix)
        else:
            pool = None

        if 'forward' in l2_device_config:
            forward = l2_device_config['forward']['mode']
        else:
            forward = None

        has_dhcp_server = (l2_device_config.get('dhcp', 'false') == 'true')

        net = Network.network_create(
            name=name,
            environment=self,
            pool=pool,
            forward=forward,
            has_dhcp_server=has_dhcp_server)
        net.define()
        return net

    def create_interfaces(self, interfaces, node,
                          model=settings.INTERFACE_MODEL):
        for interface in interfaces:

            # TODO(ddmitriev): use l2_network_devices object to get
            # the network device
            network_name = interface['l2_network_device']
            network = self.get_network(name=network_name)

            Interface.interface_create(
                network,
                node=node,
                model=model,
            )

    def create_node(self, config_node):
        node_params = config_node['params']
        node = self.add_node(
            name=config_node['name'],
            role=config_node['role'],
            memory=int(node_params['memory']),
            vcpu=int(node_params['vcpu']),
            boot=node_params['boot'])

        self.create_interfaces(node_params['interfaces'], node)

        for volume in node_params.get('volumes', None):
            volume_name = config_node['name'] + '-' + volume['name']
            if 'source_image' in volume:
                disk = self.add_empty_volume(
                    node,
                    volume_name,
                    capacity=_get_file_size(volume['source_image']),
                    format=volume.get('format', 'qcow2'),
                    device=volume.get('device', 'disk'),
                    bus=volume.get('bus', 'virtio')
                )
                disk.volume.define()
                disk.volume.upload(volume['source_image'])
            else:
                disk = self.add_empty_volume(
                    node,
                    volume_name,
                    capacity=int(volume['capacity']) * 1024 ** 3,
                    format=volume.get('format', 'qcow2'),
                    device=volume.get('device', 'disk'),
                    bus=volume.get('bus', 'virtio')
                )
                disk.volume.define()

        node.define()
        return node

#==============================================================


# LEGACY
    @classmethod
    def describe_environment(cls, boot_from='cdrom'):
        """This method is DEPRECATED.

           Reserved for backward compatibility only.
           Please use self.create_environment() instead.
        """
        if settings.DEVOPS_SETTINGS_TEMPLATE:
            config = get_devops_config(
                settings.DEVOPS_SETTINGS_TEMPLATE)
        else:
            config = create_devops_config(
                boot_from=boot_from,
                env_name=settings.ENV_NAME,
                admin_vcpu=settings.HARDWARE["admin_node_cpu"],
                admin_memory=settings.HARDWARE["admin_node_memory"],
                admin_sysvolume_capacity=settings.ADMIN_NODE_VOLUME_SIZE,
                admin_iso_path=settings.ISO_PATH,
                nodes_count=settings.NODES_COUNT,
                slave_vcpu=settings.HARDWARE["slave_node_cpu"],
                slave_memory=settings.HARDWARE["slave_node_memory"],
                slave_volume_capacity=settings.NODE_VOLUME_SIZE,
                use_all_disks=settings.USE_ALL_DISKS,
                ironic_nodes_count=settings.IRONIC_NODES_COUNT,
                networks_bonding=settings.BONDING,
                networks_bondinginterfaces=settings.BONDING_INTERFACES,
                networks_multiplenetworks=settings.MULTIPLE_NETWORKS,
                networks_nodegroups=settings.NODEGROUPS,
                networks_interfaceorder=settings.INTERFACE_ORDER,
                networks_pools=settings.POOLS,
                networks_forwarding=settings.FORWARDING,
                networks_dhcp=settings.DHCP,
            )

        environment = cls.create_environment(config)
        return environment


    @classmethod
    def create_environment(cls, full_config):
        """Create a new environment using full_config object

        :param full_config: object that describes all the parameters of
                            created environment
            :rtype: Environment
        """

        config = full_config['template']['devops_settings']
        environment = cls.create(config['env_name'])

        # create groups and drivers
        groups = config['groups']
        environment.add_groups(groups)

        # create address pools
        address_pools = config['address_pools']
        environment.add_address_pools(address_pools)
#        # TODO(ddmitriev): link the dict config['address_pools'] to the
#        # 'environment' object.
#        address_pools = config['address_pools']

        # process group items
        for group_data in groups:
            group = environment.get_group(name=group_data['name'])

            # add l2_network_devices
            group.add_l2_network_devices(
                group_data.get('l2_network_devices', {}))

            # add network_pools
            group.add_network_pools(
                group_data.get('network_pools', {}))

            # add nodes
            group.add_nodes(
                group_data.get('nodes', []))


#        # Create networks:
#        for group in config['groups']:
#            # TODO(ddmitriev): use group['driver'] as a driver for
#            # manage networks and nodes in the group
#
#            # TODO(ddmitriev): link the dict group['network_pools'] to 'group'
#            # object.

#            for l2_device_name in group['l2_network_devices']:
#                l2_device_config = group['l2_network_devices'][l2_device_name]
#                environment.create_networks(
#                    name=l2_device_name,
#                    l2_device_config=l2_device_config,
#                    address_pools=address_pools)

        # Create nodes:
#        for group in config['groups']:
#            # TODO(ddmitriev): use group['driver'] as a driver for
#            # manage networks and nodes in the group
#            for config_node in group['nodes']:
#                environment.create_node(config_node)

        return environment


# LEGACY
    # Rename it to default_gw and move to models.Network class
    def router(self, router_name=None):  # Alternative name: get_host_node_ip
        router_name = router_name or self.admin_net
        if router_name == self.admin_net2:
            return str(self.get_network(name=router_name).ip[2])
        return str(self.get_network(name=router_name).ip[1])

# LEGACY
    # @logwrap
    def get_admin_remote(self,
                         login=settings.SSH_CREDENTIALS['login'],
                         password=settings.SSH_CREDENTIALS['password']):
        """SSH to admin node

        :rtype : SSHClient
        """
        return self.nodes().admin.remote(
            self.admin_net,
            login=login,
            password=password)

# LEGACY
    # @logwrap
    def get_ssh_to_remote(self, ip):
        keys = []
        for key_string in ['/root/.ssh/id_rsa',
                           '/root/.ssh/bootstrap.rsa']:
            with self.get_admin_remote().open(key_string) as f:
                keys.append(RSAKey.from_private_key(f))

        return SSHClient(ip,
                         username=settings.SSH_CREDENTIALS['login'],
                         password=settings.SSH_CREDENTIALS['password'],
                         private_keys=keys)

# LEGACY
    # @logwrap
    def get_ssh_to_remote_by_key(self, ip, keyfile):
        try:
            with open(keyfile) as f:
                keys = [RSAKey.from_private_key(f)]
        except IOError:
            logger.warning('Loading of SSH key from file failed. Trying to use'
                           ' SSH agent ...')
            keys = Agent().get_keys()
        return SSHClient(ip, private_keys=keys)

# LEGACY
    def nodes(self):  # migrated from EnvironmentModel.nodes()
        # DEPRECATED. Please use environment.get_nodes() instead.
        return Nodes(self)


# LEGACY CLASS
class Nodes(object):
    def __init__(self, environment):
        self.admins = sorted(
            list(environment.get_nodes(role='fuel_master')),
            key=lambda node: node.name
        )
        self.others = sorted(
            list(environment.get_nodes(role='fuel_slave')),
            key=lambda node: node.name
        )
        self.ironics = sorted(
            list(environment.get_nodes(role='ironic')),
            key=lambda node: node.name
        )
        self.slaves = self.others
        self.all = self.slaves + self.admins + self.ironics
        self.admin = self.admins[0]

    def __iter__(self):
        return self.all.__iter__()
