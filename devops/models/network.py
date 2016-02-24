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
from ipaddr import IPNetwork
import jsonfield

from django.db import IntegrityError
from django.db import models
from django.db import transaction

from devops import logger
from devops.error import DevopsError
from devops.helpers.helpers import generate_mac
from devops.helpers.network import IpNetworksPool
from devops.models.base import BaseModel
from devops.models.base import choices
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
    ip_ranges = ParamField(default={})    # {'range_a': ('x.x.x.x', 'y.y.y.y'),
                                          #  'range_b': ('a.a.a.a', 'b.b.b.b'), ...}
    ip_reserved = ParamField(default={})  # {'gateway': 'n.n.n.1', 'local_ip': 'm.m.m.254'}

    # NEW. Warning: Old implementation returned self.net
    @property
    def ip_network(self):
        """Return IPNetwork representation of self.ip_network field.

        :return: IPNetwork()
        """
        return IPNetwork(self.net)

    def ip_range_start(self, range_name):
        """Return the IP address of start the IP range 'range_name'

        :return: str
        """
        if range_name in self.ip_ranges:
            return str(self.ip_ranges.get(range_name)[0])
        else:
            logger.debug("IP range '{0}' not found in the "
                         "address pool {1}".format(range_name, self.name))
            return None

    def ip_range_end(self, range_name):
        """Return the IP address of end the IP range 'range_name'

        :return: str
        """
        if range_name in self.ip_ranges:
            return str(self.ip_ranges.get(range_name)[1])
        else:
            logger.debug("IP range '{0}' not found in the "
                         "address pool {1}".format(range_name, self.name))
            return None

    def get_ip(self, ip_name):
        """Return the reserved IP
           For example, 'gateway' is one of the common reserved IPs

        :return: str
        """
        if ip_name in self.ip_reserved:
            return str(self.ip_reserved.get(ip_name))
        else:
            logger.debug("Reserved IP '{0}' not found in the "
                         "address pool {1}".format(ip_name, self.name))
            return None

    def next_ip(self):
        for ip in self.ip_network.iterhosts():
            # if ip < self.ip_pool_start or ip > self.ip_pool_end:
            # Skip net, gw and broadcast addresses in the address pool
            if ip < self.ip_network[2] or ip > self.ip_network[-2]:
                continue
            already_exists = Address.objects.filter(
                interface__l2_network_device__address_pool=self,
                ip_address=str(ip)).exists()
            if already_exists:
                continue
            return ip
        raise DevopsError("No more free addresses in the address pool {0}"
                          " with CIDR {1}".format(self.name, self.net))

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
    def address_pool_create(cls, name, environment, pool=None, **params):
        """Create network

        :rtype : Network
        """
        if pool is None:
            pool = IpNetworksPool(
                networks=[IPNetwork('10.0.0.0/16')],
                prefix=24,
                allocated_networks=environment.get_allocated_networks())

        address_pool = cls._safe_create_network(
            environment=environment,
            name=name,
            pool=pool,
            **params
        )

        # Translate indexes into IP addresses for ip_reserved and ip_ranges
        def _relative_to_ip(ip_network, ip_id):
            """Get an IP from IPNetwork ip's list by index

            :param ip_network: IPNetwork object
            :param ip_id: string, if contains '+' or '-' then it is
                          used as index of an IP address in ip_network,
                          else it is considered as IP address.

            :rtype : str(IP)
            """
            if type(ip_id) == int:
                return str(ip_network[int(ip_id)])
            else:
                return str(ip_id)

        if 'ip_reserved' in params:
            for ip_res in params['ip_reserved'].keys():
                ip = _relative_to_ip(address_pool.ip_network,
                                     params['ip_reserved'][ip_res])
                params['ip_reserved'][ip_res] = ip      # Store to template
                address_pool.ip_reserved[ip_res] = ip   # Store to the object

        if 'ip_ranges' in params:
            for ip_range in params['ip_ranges']:
                ipr_start = _relative_to_ip(address_pool.ip_network,
                                            params['ip_ranges'][ip_range][0])
                ipr_end = _relative_to_ip(address_pool.ip_network,
                                          params['ip_ranges'][ip_range][1])
                params['ip_ranges'][ip_range] = (ipr_start, ipr_end)
                address_pool.ip_ranges[ip_range] = (ipr_start, ipr_end)

        return address_pool


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
    address_pool = models.ForeignKey('AddressPool', null=True)
    name = models.CharField(max_length=255)

    @property
    def driver(self):
        return self.group.driver

    @property
    def interfaces(self):
        return self.interface_set.all()

    def define(self):
        self.save()

    def start(self):
        pass

    def destroy(self):
        pass

    def erase(self):
        self.remove(verbose=False)

    def remove(self, verbose=False):
        self.delete()


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
        if interface.l2_network_device.address_pool is not None:
            interface.add_address()
        return interface


class Address(models.Model):
    class Meta(object):
        db_table = 'devops_address'
        app_label = 'devops'

    interface = models.ForeignKey('Interface', null=True)
    ip_address = models.GenericIPAddressField()
