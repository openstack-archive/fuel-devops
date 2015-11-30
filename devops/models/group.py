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

from copy import deepcopy
import time

from paramiko import Agent
from paramiko import RSAKey
from django.db import models
from django.conf import settings

from devops import logger
from devops.helpers.helpers import _get_file_size
from devops.helpers.helpers import SSHClient
from devops.models.base import BaseModel
from devops.models.node import Node
from devops.models.network import NetworkPool
from devops.models.network import Address_Pool
from devops.models.volume import Volume
from devops.models.volume import DiskDevice
from devops.models.driver import Driver


class Group(BaseModel):
    """Groups nodes controlled by a specific driver
    """

    class Meta(object):
        db_table = 'devops_group'
        app_label = 'devops'

    environment = models.ForeignKey('Environment', null=True)
    name = models.CharField(max_length=255)
    driver = models.OneToOneField('Driver', primary_key=True)

    def get_l2_network_device(self, *args, **kwargs):
        return self.l2_network_device_set.get(*args, **kwargs)

    def get_l2_network_devices(self, *args, **kwargs):
        return self.l2_network_device_set.filter(*args, **kwargs)

    def get_network_pool(self, *args, **kwargs):
        return self.network_pool_set.get(*args, **kwargs)

    def get_network_pools(self, *args, **kwargs):
        return self.network_pool_set.filter(*args, **kwargs)

    def get_node(self, *args, **kwargs):
        return self.node_set.get(*args, **kwargs)

    def get_nodes(self, *args, **kwargs):
        return self.node_set.filter(*args, **kwargs)

#  NEW, TO ENV?
    def get_allocated_networks(self):
        return self.driver.get_allocated_networks()

    # TO REMOVE
    def add_empty_volume(self, node, name,
                         capacity=50 * 1024 ** 3,
                         device='disk', bus='virtio', format='qcow2'):
        return DiskDevice.node_attach_volume(
            node=node,
            volume=Volume.volume_create(
                name=name,
                capacity=capacity,
#                group=self,
                node=node,
                format=format),
            device=device,
            bus=bus)

    @classmethod
    def group_create(cls, **kwargs):
        """Create Group instance

        :rtype: devops.models.Group
        """
        return cls.objects.create(**kwargs)

    @classmethod
    def get(cls, *args, **kwargs):
        return cls.objects.get(*args, **kwargs)

    @classmethod
    def list_all(cls):
        return cls.objects.all()

    def has_snapshot(self, name):
        return all(n.has_snapshot(name) for n in self.get_nodes())

    def define(self):
        for l2_network_device in self.get_l2_network_devices():
            l2_network_device.define()
        for node in self.get_nodes():
            for volume in node.get_volumes():
                volume.define()
            node.define()

    def start(self, nodes=None):
        for l2_network_device in self.get_l2_network_devices():
            l2_network_device.start()
        for node in nodes or self.get_nodes():
            node.start()

    def destroy(self, verbose=False):
        for node in self.get_nodes():
            node.destroy(verbose=verbose)

    def erase(self):
        for node in self.get_nodes():
            node.erase()
            # ??? ############################################
            for volume in node.get_volumes():
                volume.erase()
        for l2_network_device in self.get_l2_network_devices():
            l2_network_device.erase()
        self.delete()

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
        if (flag and not self.has_snapshot(name)):
            raise Exception("some nodes miss snapshot,"
                            " test should be interrupted")
        for node in self.get_nodes():
            node.revert(name, destroy=False)

    # TO REMOVE
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
        #  Disabled untill a safer implmentation arrives

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

    # NEW
    def add_l2_network_devices(self, l2_network_devices):
        for name, data in l2_network_devices.items():
            params = data.get('params', {})
            address_pool = self.environment.get_address_pool(name=data['address_pool'])

            cls = self.driver.get_model_class('L2_Network_Device')
            cls.objects.create(
                group=self,
                name=name,
                address_pool=address_pool,
                **params
            )

    # NEW
    def add_nodes(self, nodes):
        for node_cfg in nodes:
            new_node_cfg = deepcopy(node_cfg)
            interfaces = new_node_cfg['params'].pop('interfaces', [])
            network_configs = new_node_cfg['params'].pop('network_config', [])
            volumes = new_node_cfg['params'].pop('volumes', [])

            node = self.add_node(
                name=new_node_cfg['name'],
                role=new_node_cfg['role'],
                **new_node_cfg['params']
            )

            node.add_interfaces(interfaces)
            node.add_network_configs(network_configs)
            node.add_volumes(volumes)

    # REWRITEN
    def add_node(self, name, role='slave', **params):
        cls = self.driver.get_model_class('Node', subtype=role)
        return cls.objects.create(
            group=self,
            name=name,
            role=role,
            **params
        )

    # NEW
    def add_network_pools(self, network_pools):
        for pool_name, address_pool_name in network_pools.items():
            pass

    # NEW
    def add_network_pool(self, name, address_pool_name):
        address_pool = self.environment.get_address_pool(
            name=address_pool_name)

        NetworkPool.objects.create(
            group=self,
            name=name,
            address_pool=address_pool,
        )

    # TO REMOVE
    def describe_empty_node(self, name, networks):
        node = self.add_node(
            name=name,
            memory=settings.HARDWARE["slave_node_memory"],
            vcpu=settings.HARDWARE["slave_node_cpu"],
            role='slave')
        self.create_interfaces(networks, node)
        self.add_empty_volume(node, name + '-system')

        if settings.USE_ALL_DISKS:
            self.add_empty_volume(node, name + '-cinder')
            self.add_empty_volume(node, name + '-swift')

        return node

    # TO REMOVE
    def describe_admin_node(self, name, networks, boot_from='cdrom',
                            vcpu=None, memory=None,
                            iso_path=None):
        if boot_from == 'cdrom':
            boot_device = ['hd', 'cdrom']
            device = 'cdrom'
            bus = 'ide'
        elif boot_from == 'usb':
            boot_device = ['hd']
            device = 'disk'
            bus = 'usb'

        node = self.add_node(
            memory=memory or settings.HARDWARE["admin_node_memory"],
            vcpu=vcpu or settings.HARDWARE["admin_node_cpu"],
            name=name,
            role='admin',
            boot=boot_device)
        self.create_interfaces(networks, node)

#        if self.os_image is None:
        iso = iso_path or settings.ISO_PATH
        self.add_empty_volume(node, name + '-system',
                              capacity=settings.ADMIN_NODE_VOLUME_SIZE
                              * 1024 ** 3)
        self.add_empty_volume(
            node,
            name + '-iso',
            capacity=_get_file_size(iso),
            format='raw',
            device=device,
            bus=bus)
#        else:
#            volume = Volume.volume_get_predefined(self.os_image)
#            vol_child = Volume.volume_create_child(
#                name=name + '-system',
#                backing_store=volume,
#                node=node,
#            )
#            DiskDevice.node_attach_volume(
#                node=node,
#                volume=vol_child
#            )
        return node

    # TO REWRITE
    # Rename it to default_gw and move to models.Network class
    def router(self, router_name=None):  # Alternative name: get_host_node_ip
        router_name = router_name or self.environment.admin_net
        if router_name == self.environment.admin_net2:
            return str(self.get_network(name=router_name).ip[2])
        return str(self.get_network(name=router_name).ip[1])

    # TO ENV
    def get_admin_remote(self,
                         login=settings.SSH_CREDENTIALS['login'],
                         password=settings.SSH_CREDENTIALS['password']):
        """SSH to admin node

        :rtype : SSHClient
        """
        return self.nodes().admin.remote(
            self.environment.admin_net,
            login=login,
            password=password)

    # TO ENV
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

    # TO ENV
    def get_ssh_to_remote_by_key(self, ip, keyfile):
        try:
            with open(keyfile) as f:
                keys = [RSAKey.from_private_key(f)]
        except IOError:
            logger.warning('Loading of SSH key from file failed. Trying to use'
                           ' SSH agent ...')
            keys = Agent().get_keys()
        return SSHClient(ip, private_keys=keys)


# TODO: move to env
class Env(object):

#    def get_address_pool(self, *args, **kwargs):
#        return self.address_pool_set.get(*args, **kwargs)

#    def get_address_pools(self, *args, **kwargs):
#        return self.address_pool_set.filter(*args, **kwargs)

#    def get_group(self, *args, **kwargs):
#        return self.group_set.get(*args, **kwargs)

#    def get_groups(self, *args, **kwargs):
#        return self.group_set.filter(*args, **kwargs)

#    def get_node(self, *args, **kwargs):
#        return Node.objects.get(*args, group__environment=self, **kwargs)

#    def get_nodes(self, *args, **kwargs):
#        return Node.objects.filter(*args, group__environment=self, **kwargs)

    def get_admin_node(self):
        return self.get_node(role='admin')

    def get_allocated_networks(self):
        allocated_networks = []
        for group in self.get_groups():
            allocated_networks += group.get_allocated_networks()
        return allocated_networks

#    @classmethod
#    def create_environment(cls, full_config):
#        config = full_config['template']['devops_settings']
#        env = cls.create(config['env_name'])

#        # create groups and drivers
#        groups = config['groups']
#        env.add_groups(groups)

        # create address pools
#        address_pools = config['address_pools']
#        env.add_address_pools(address_pools)

        # process group items
#        for group_name, group_data in groups.iteritems():
#            group = env.get_group(name=group_name)

            # add l2_network_devices
#            group.add_l2_network_devices(
#                group_data.get('l2_network_devices', {}))

            # add network_pools
#            group.add_network_pools(
#                group_data.get('network_pools', {}))

            # add nodes
#            group.add_nodes(
#                group_data.get('nodes', []))

#        return env

#    def add_groups(self, groups):
#        for group_name, group_data in groups.iteritems():
#            driver_data = group_data['driver']
#            self.add_group(
#                group_name=group_name,
#                driver_name=driver_data['name'],
#                **driver_data.get('params', {})
#            )

#    def add_group(self, group_name, driver_name, **driver_params):
#        driver = Driver.driver_create(
#            name=driver_name,
#            **driver_params
#        )
#        return Group.group_create(
#            name=group_name,
#            environment=self,
#            driver=driver,
#        )

#    def add_address_pools(self, address_pools):
#        for name, data in address_pools.iteritems():
#            self.add_address_pool(
#                name=name,
#                pool=data['net'],
#                **data.get('params', {})
#            )

#    def add_address_pool(self, name, net, **params):
#        Address_Pool.address_pool_create(
#            environment=self,
#            name=name,
#            net=net,
#            **params
#        )

#    def define(self):
#        for group in self.get_groups():
#            group.define()

#    def start(self, nodes=None):
#        for group in self.get_groups():
#            group.start(nodes)

#    def destroy(self):
#        for group in self.get_groups():
#            group.destroy()

#    def erase(self):
#        for group in self.get_groups():
#            group.erase()
