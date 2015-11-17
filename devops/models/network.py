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

import jsonfield
from django.conf import settings
from django.db import IntegrityError
from django.db import models
from django.db import transaction

from devops.helpers.helpers import generate_mac
from devops.helpers.network import IpNetworksPool, DevopsIPNetwork
from devops.models.base import choices
from devops.models.base import BaseModel, ParamedModel


class AddressPool(ParamedModel, BaseModel):
    class Meta:
        unique_together = ('name', 'environment')
        db_table = 'devops_address_pool'

    environment = models.ForeignKey('Environment', null=True)
    name = models.CharField(max_length=255)
    net = models.CharField(max_length=255, unique=True)

    @property
    def ip_network(self):
        """Return DevopsIPNetwork representation of self.net field.

        :return: DevopsIPNetwork()
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

    def create_network_pool(self, networks, prefix, allocated_networks):
        """Create network pool

        :rtype : IpNetworksPool
        """
        return IpNetworksPool(
            networks=networks,
            prefix=prefix,
            allocated_networks=allocated_networks)

    @classmethod
    @transaction.commit_on_success
    def _safe_create_network(cls, name, pool, environment=None):
        for ip_network in pool:
            try:
                if cls.objects.filter(net=str(ip_network)).exists():
                    continue
                return cls.objects.create(
                    environment=environment,
                    name=name,
                    net=ip_network,
                )
            except IntegrityError:
                transaction.rollback()

    @classmethod
    def network_create(cls, name, environment=None,
                       ip_network=None, pool=None):
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
            pool = cls.create_network_pool(
                networks=[DevopsIPNetwork('10.0.0.0/16')],
                prefix=24)
        return cls._safe_create_network(
            environment=environment,
            name=name,
            pool=pool)

    @classmethod
    def create_networks(cls, environment, network_names=None,
                        pool=None):
        """Create several networks

        :param environment: Environment
        :param network_names: List
        :param has_dhcp: Bool
        :param has_pxe: Bool
        :param forward: String
        :param pool: IpNetworksPool
            :rtype : List
        """
        if network_names is None:
            network_names = settings.DEFAULT_INTERFACE_ORDER.split(',')
        networks = []
        for name in network_names:
            net = cls.network_create(name=name,
                                     environment=environment,
                                     pool=pool)
            networks.append(net)
        return networks


class NetworkPool(BaseModel):
    class Meta:
        db_table = 'devops_network_pool'

    group = models.ForeignKey('AddressPool', null=True)
    address_pool = models.ForeignKey('Environment', null=True)
    name = models.CharField(max_length=255)


class L2NetworkDevice(ParamedModel, BaseModel):
    class Meta:
        db_table = 'devops_l2_network_device'

    group = models.ForeignKey('group', null=True)
    address_pool = models.ForeignKey('AddressPool', null=True)
    name = models.CharField(max_length=255)

    @property
    def driver(self):
        self.group.driver

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
    class Meta:
        db_table = 'devops_network_config'

    node = models.ForeignKey('Node', null=False)
    label = models.CharField(max_length=255, null=False)
    networks = jsonfield.JSONField()
    # TODO:


class Interface(models.Model):
    class Meta:
        db_table = 'devops_interface'

    node = models.ForeignKey('Node')
    l2_network_device = models.ForeignKey('L2NetworkDevice')
    label = models.CharField(max_length=255, null=False)
    mac_address = models.CharField(max_length=255, unique=True, null=False)
    type = models.CharField(max_length=255, null=False)
    model = choices('virtio', 'e1000', 'pcnet', 'rtl8139', 'ne2k_pci')

    @property
    def target_dev(self):
        return self.label

    @property
    def addresses(self):
        return self.address_set.all()

    @staticmethod
    def interface_create(l2_network_device, node, type='network',
                         mac_address=None, model='virtio',
                         interface_map={}):
        """Create interface

        :rtype : Interface
        """
        interfaces = []

        def _create(mac_addr=None):
            interface = Interface.objects.create(
                l2_network_device=l2_network_device,
                node=node,
                type=type,
                mac_address=mac_addr or generate_mac(),
                model=model)
            ip = l2_network_device.address_pool.next_ip()
            Address.objects.create(ip_address=str(ip),
                                   interface=interface)
            return interface

        if interface_map:
            if len(interface_map[l2_network_device.name]) > 0:
                for _ in interface_map[l2_network_device.name]:
                    interfaces.append(_create())
                return interfaces
        else:
            return _create(mac_address)


class Address(models.Model):
    class Meta:
        db_table = 'devops_address'

    interface = models.ForeignKey('Interface')
    ip_address = models.GenericIPAddressField()
