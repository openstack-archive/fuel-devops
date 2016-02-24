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

from devops.error import DevopsError
from devops.helpers.helpers import generate_mac
from devops.helpers.network import IpNetworksPool
from devops import logger
from devops.models.base import BaseModel
from devops.models.base import choices
from devops.models.base import ParamedModel
from devops.models.base import ParamField


class AddressPool(ParamedModel, BaseModel):
    """Address pool

    Template example (address_pools):
    -----------------

    address_pools:

      fuelweb_admin-pool01:
        net: 172.0.0.0/16:24
        params:
          tag: 0
          ip_reserved:
            gateway: 1
            l2_network_device: 1  # l2_network_device will get the
                                  # IP address = 172.0.*.1  (net + 1)
          ip_ranges:
            default: [2, -2]     # admin IP range for 'default' nodegroup name

      public-pool01:
        net: 12.34.56.0/26    # Some WAN routed to the test host.
        params:
          tag: 100
          ip_reserved:
            gateway: 12.34.56.1
            l2_network_device: 12.34.56.62 # l2_network_device will be assumed
                                           # with this IP address.
                                           # It will be used for create libvirt
                                           # network if libvirt driver is used.
          ip_ranges:
            default: [2, 127]   # public IP range for 'default' nodegroup name
            floating: [128, -2] # floating IP range

      storage-pool01:
        net: 172.0.0.0/16:24
        params:
          tag: 101
          ip_reserved:
            l2_network_device: 1  # 172.0.*.1

      management-pool01:
        net: 172.0.0.0/16:24
        params:
          tag: 102
          ip_reserved:
            l2_network_device: 1  # 172.0.*.1

      private-pool01:
        net: 192.168.0.0/24:26
        params:
          tag: 103
          ip_reserved:
            l2_network_device: 1  # 192.168.*.1

    """
    class Meta(object):
        unique_together = ('name', 'environment')
        db_table = 'devops_address_pool'
        app_label = 'devops'

    environment = models.ForeignKey('Environment')
    name = models.CharField(max_length=255)
    net = models.CharField(max_length=255, unique=True)
    tag = ParamField(default=0)

    # ip_reserved = {'l2_network_device': 'm.m.m.50',
    #                'gateway': 'n.n.n.254', ...}
    ip_reserved = ParamField(default={})

    # ip_ranges = {'range_a': ('x.x.x.x', 'y.y.y.y'),
    #              'range_b': ('a.a.a.a', 'b.b.b.b'), ...}
    ip_ranges = ParamField(default={})

    # NEW. Warning: Old implementation returned self.net
    @property
    def ip_network(self):
        """Return IPNetwork representation of self.ip_network field.

        :return: IPNetwork()
        """
        return IPNetwork(self.net)

    def ip_range_start(self, range_name):
        """Return the IP address of start the IP range 'range_name'

        :return: str(IP) or None
        """
        if range_name in self.ip_ranges:
            return str(self.ip_ranges.get(range_name)[0])
        else:
            logger.debug("IP range '{0}' not found in the "
                         "address pool {1}".format(range_name, self.name))
            return None

    def ip_range_end(self, range_name):
        """Return the IP address of end the IP range 'range_name'

        :return: str(IP) or None
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

        :return: str(IP) or None
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

        address_pool.save()
        return address_pool


class NetworkPool(BaseModel):
    """Network pools for mapping logical (OpenStack) networks and AddressPools

    This object is not used for environment creation, only for mapping some
    logical networks with AddressPool objects for each node group.

    The same network (for example: 'public') that is used in different node
    groups, can be mapped on the same AddressPool for all node groups, or
    different AddressPools can be specified for each node group:

    Template example (network_pools):
    -----------------

    groups:
     - name: default

       network_pools:  # Address pools for OpenStack networks.
         # Actual names should be used for keys
         # (the same as in Nailgun, for example)

         fuelweb_admin: fuelweb_admin-pool01
         public: public-pool01
         storage: storage-pool01
         management: management-pool01
         private: private-pool01

     - name: second_node_group

       network_pools:
         # The same address pools for admin/PXE and management networks
         fuelweb_admin: fuelweb_admin-pool01
         management: management-pool01

         # Another address pools for public, storage and private
         public: public-pool02
         storage: storage-pool02
         private: private-pool02


    :attribute name: name of one of the OpenStack(Nailgun) networks
    :attribute address_pool: key for the 'address_pool' object
    :attribute group: key for the 'group' object
    """
    class Meta(object):
        db_table = 'devops_network_pool'
        app_label = 'devops'

    group = models.ForeignKey('Group', null=True)
    address_pool = models.ForeignKey('AddressPool', null=True)
    name = models.CharField(max_length=255)

    def ip_range(self, range_name=None):
        """Get IP range for the network pool

        :param range_name: str or None.
                           If None - group.name is used as a default range.
        :return: touple of two IPs for the range - ('x.x.x.x', 'y.y.y.y')
                 or None.
        """
        if range_name is None:
            return (self.address_pool.ip_range_start(self.group.name),
                    self.address_pool.ip_range_end(self.group.name))
        else:
            return (self.address_pool.ip_range_start(range_name),
                    self.address_pool.ip_range_end(range_name))

    @property
    def gateway(self):
        """Get the network gateway

        :return: reserved IP address with key 'gateway', or None
        """
        return self.address_pool.get_ip('gateway')

    @property
    def vlan_start(self):
        """Get the network VLAN tag ID or start ID of VLAN range

        :return: int
        """
        return self.address_pool.tag

    @property
    def vlan_end(self):
        """Get end ID of VLAN range

        :return: int
        """
        return None

    @property
    def net(self):
        """Get the network CIDR

        :return: str('x.x.x.x/y')
        """
        return self.address_pool.net


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
