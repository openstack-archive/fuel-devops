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

from django.db import models

from devops import logger
from devops.models.base import BaseModel
from devops.models.network import NetworkPool


class Group(BaseModel):
    """Groups nodes controlled by a specific driver"""

    class Meta(object):
        db_table = 'devops_group'
        app_label = 'devops'

    environment = models.ForeignKey('Environment', null=True)
    name = models.CharField(max_length=255)
    driver = models.OneToOneField('Driver', primary_key=True)

    def get_l2_network_device(self, **kwargs):
        return self.l2networkdevice_set.get(**kwargs)

    def get_l2_network_devices(self, **kwargs):
        return self.l2networkdevice_set.filter(**kwargs)

    def get_network_pool(self, **kwargs):
        return self.networkpool_set.get(**kwargs)

    def get_network_pools(self, **kwargs):
        return self.networkpool_set.filter(**kwargs)

    def get_node(self, **kwargs):
        return self.node_set.get(**kwargs)

    def get_nodes(self, **kwargs):
        return self.node_set.filter(**kwargs)

    def get_allocated_networks(self):
        return self.driver.get_allocated_networks()

    @classmethod
    def group_create(cls, **kwargs):
        """Create Group instance

        :rtype: devops.models.Group
        """
        return cls.objects.create(**kwargs)

    @classmethod
    def get(cls, **kwargs):
        return cls.objects.get(**kwargs)

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

        for l2_network_device in self.get_l2_network_devices():
            l2_network_device.erase()
        self.delete()

    @classmethod
    def erase_empty(cls):
        for env in cls.list_all():
            if env.get_nodes().count() == 0:
                env.erase()

    # TO REWRITE FOR LIBVIRT DRIVER
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
            params = deepcopy(data)
            self.add_l2_network_device(
                name=name,
                address_pool_name=params.pop('address_pool'),
                **params
            )

    # NEW
    def add_l2_network_device(self, name, address_pool_name, **params):
        address_pool = self.environment.get_address_pool(
            name=address_pool_name)

        cls = self.driver.get_model_class('L2NetworkDevice')
        return cls.objects.create(
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
            network_configs = new_node_cfg['params'].pop('network_config', {})
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
    def add_node(self, name, role='fuel_slave', **params):
        cls = self.driver.get_model_class('Node')
        return cls.objects.create(
            group=self,
            name=name,
            role=role,
            **params
        )

    # NEW
    def add_network_pools(self, network_pools):
        for pool_name, address_pool_name in network_pools.items():
            self.add_network_pool(
                name=pool_name,
                address_pool_name=address_pool_name,
            )

    # NEW
    def add_network_pool(self, name, address_pool_name):
        address_pool = self.environment.get_address_pool(
            name=address_pool_name)

        NetworkPool.objects.create(
            group=self,
            name=name,
            address_pool=address_pool,
        )
