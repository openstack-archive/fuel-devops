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
import jsonfield
from ipaddr import IPNetwork

from django.db import IntegrityError
from django.db import models
from django.db import transaction

from devops.error import DevopsError
from devops.helpers.helpers import generate_mac
from devops.helpers.network import IpNetworksPool
from devops.helpers.network import DevopsIPNetwork
from devops.models.base import choices
from devops.models.base import BaseModel
from devops.models.base import ParamedModel
from devops.models.base import ParamField


class AddressPool(ParamedModel, BaseModel):
    class Meta(object):
        unique_together = ('name', 'environment')
        db_table = 'devops_address_pool'
        app_label = 'devops'

    environment = models.ForeignKey('Environment')
    name = models.CharField(max_length=255)
    net = models.CharField(max_length=255, unique=True)
    tag = ParamField(default=0)

    # NEW. Warning: Old implementation returned self.net
    @property
    def ip_network(self):
        """Return IPNetwork representation of self.ip_network field.

        :return: IPNetwork()
        """
        return DevopsIPNetwork(self.net)

    def next_ip(self):
        ip_net = self.ip_network
        for ip in ip_net.iterhosts():
            if ip < ip_net.ip_start or ip > ip_net.ip_end:
                continue
            already_exists = Address.objects.filter(
                interface__l2_network_device__address_pool=self,
                ip_address=str(ip)).exists()
            if already_exists:
                continue
            return ip
        raise DevopsError("No more free addresses in the address pool {0} with CIDR {1}".format(self.name, self.net))

    @classmethod
    @transaction.commit_on_success
    def _safe_create_network(cls, name, pool, environment, **params):
        for ip_network in pool:
            try:
                if cls.objects.filter(net=str(ip_network)).exists():
                    continue

                new_params = deepcopy(params)
                new_params['net'] = ip_network
                return cls.objects.create(
                    environment=environment,
                    name=name,
                    **new_params
                )
            except IntegrityError:
                transaction.rollback()

    @classmethod
    def address_pool_create(cls, name, environment,
                            ip_network=None, pool=None, **params):
        """Create network

        :rtype : Network
        """
        if ip_network:
            return cls.objects.create(
                environment=environment,
                name=name,
                net=ip_network,
            )
        if pool is None:
            pool = IpNetworksPool(
                networks=[IPNetwork('10.0.0.0/16')],
                prefix=24,
                allocated_networks=environment.get_allocated_networks())
        return cls._safe_create_network(
            environment=environment,
            name=name,
            pool=pool,
            **params
        )


class NetworkPool(BaseModel):
    class Meta(object):
        db_table = 'devops_network_pool'
        app_label = 'devops'

    group = models.ForeignKey('Group', null=True)
    address_pool = models.ForeignKey('AddressPool', null=True)
    name = models.CharField(max_length=255)


class L2NetworkDevice(ParamedModel, BaseModel):
    class Meta(object):
        db_table = 'devops_l2_network_device'
        app_label = 'devops'

    group = models.ForeignKey('Group', null=True)
    address_pool = models.ForeignKey('AddressPool')
    name = models.CharField(max_length=255)

    @property
    def driver(self):
        return self.group.driver

    @property
    def interfaces(self):
        return self.interface_set.all()

    def define(self):
        pass

    def start(self):
        pass

    def destroy(self):
        pass

    def erase(self):
        pass


class NetworkConfig(models.Model):
    class Meta(object):
        db_table = 'devops_network_config'
        app_label = 'devops'

    node = models.ForeignKey('Node')
    label = models.CharField(max_length=255, null=False)
    networks = jsonfield.JSONField(default=[])
    aggregation = models.CharField(max_length=255, null=True)
    parents = jsonfield.JSONField(default=[])


class Interface(models.Model):
    class Meta(object):
        db_table = 'devops_interface'
        app_label = 'devops'

    node = models.ForeignKey('Node')
    l2_network_device = models.ForeignKey('L2NetworkDevice', null=True)
    label = models.CharField(max_length=255, null=True)
    mac_address = models.CharField(max_length=255, unique=True, null=False)
    type = models.CharField(max_length=255, null=False)
    model = choices('virtio', 'e1000', 'pcnet', 'rtl8139', 'ne2k_pci')

    @property
    def target_dev(self):
        return self.label

    @property
    def addresses(self):
        return self.address_set.all()

    def add_address(self):
        ip = self.l2_network_device.address_pool.next_ip()
        Address.objects.create(
            ip_address=str(ip),
            interface=self,
        )

    @staticmethod
    def interface_create(l2_network_device, node, label, type='network',
                         mac_address=None, model='virtio'):
        """Create interface

        :rtype : Interface
        """
        interface = Interface.objects.create(
            l2_network_device=l2_network_device,
            node=node,
            label=label,
            type=type,
            mac_address=mac_address or generate_mac(),
            model=model)
        interface.add_address()
        return interface


class Address(models.Model):
    class Meta(object):
        db_table = 'devops_address'
        app_label = 'devops'

    interface = models.ForeignKey('Interface', null=True)
    ip_address = models.GenericIPAddressField()
