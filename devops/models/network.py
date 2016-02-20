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

from django.conf import settings
from django.db import IntegrityError
from django.db import models
from django.db import transaction
from ipaddr import IPNetwork

from devops.error import DevopsError
from devops.helpers.helpers import generate_mac
from devops.helpers.network import IpNetworksPool
from devops.models.base import choices
from devops.models.base import DriverModel


class Network(DriverModel):
    class Meta(object):
        unique_together = ('name', 'environment')
        db_table = 'devops_network'

    environment = models.ForeignKey('Environment', null=True)
    name = models.CharField(max_length=255, unique=False, null=False)
    uuid = models.CharField(max_length=255)
    has_dhcp_server = models.BooleanField()
    has_pxe_server = models.BooleanField()
    has_reserved_ips = models.BooleanField(default=True)
    tftp_root_dir = models.CharField(max_length=255)
    forward = choices(
        'nat', 'route', 'bridge', 'private', 'vepa',
        'passthrough', 'hostdev', null=True)
    # 'ip_network' should be renamed to 'cidr'
    ip_network = models.CharField(max_length=255, unique=True)

    _iterhosts = None

    # Dirty trick. It should be placed on instance level of Environment class.
    default_pool = None

    @property
    def ip(self):
        """Return IPNetwork representation of self.ip_network field.

        :return: IPNetwork()
        """
        return IPNetwork(self.ip_network)

    @property
    def interfaces(self):
        return self.interface_set.all()

    @property
    def ip_pool_start(self):
        return IPNetwork(self.ip_network)[2]

    @property
    def ip_pool_end(self):
        return IPNetwork(self.ip_network)[-2]

    @property
    def netmask(self):
        return IPNetwork(self.ip_network).netmask

    @property
    def default_gw(self):
        return IPNetwork(self.ip_network)[1]

    def next_ip(self):
        while True:
            self._iterhosts = self._iterhosts or IPNetwork(
                self.ip_network).iterhosts()
            ip = self._iterhosts.next()
            if ip < self.ip_pool_start or ip > self.ip_pool_end:
                continue
            if not Address.objects.filter(
                    interface__network=self,
                    ip_address=str(ip)).exists():
                return ip

    def bridge_name(self):
        return self.driver.network_bridge_name(self)

    def define(self):
        self.driver.network_define(self)
        self.save()

    def start(self):
        self.create(verbose=False)

    def create(self, verbose=False):
        if verbose or not self.driver.network_active(self):
            self.driver.network_create(self)

    def destroy(self):
        self.driver.network_destroy(self)

    def erase(self):
        self.remove(verbose=False)

    def remove(self, verbose=False):
        if verbose or self.uuid:
            if verbose or self.driver.network_exists(self):
                if self.driver.network_active(self):
                    self.driver.network_destroy(self)
                self.driver.network_undefine(self)
        self.delete()

    @classmethod
    def create_network_pool(cls, networks, prefix):
        """Create network pool

        :rtype : IpNetworksPool
        """
        pool = IpNetworksPool(networks=networks, prefix=prefix)
        pool.set_allocated_networks(cls.get_driver().get_allocated_networks())
        return pool

    @classmethod
    def _get_default_pool(cls):
        """Get default pool. If it does not exists, create 10.0.0.0/16 pool.

        :rtype : IpNetworksPool
        """
        cls.default_pool = cls.default_pool or Network.create_network_pool(
            networks=[IPNetwork('10.0.0.0/16')],
            prefix=24)
        return cls.default_pool

    @classmethod
    @transaction.commit_on_success
    def _safe_create_network(
            cls, name, environment=None, pool=None,
            has_dhcp_server=True, has_pxe_server=False,
            forward='nat', reuse_network_pools=True):
        allocated_pool = pool or cls._get_default_pool()

        for ip_network in allocated_pool:
            try:
                if not reuse_network_pools:
                  # Skip the ip_network if it is
                  # in the database or in libvirt XMLs
                  if (cls.objects.filter(
                          ip_network=str(ip_network)).exists() or
                      ip_network in cls.get_driver().get_allocated_networks(
                          all_networks=True)):
                      continue
                return cls.objects.create(
                    environment=environment,
                    name=name,
                    ip_network=ip_network,
                    has_pxe_server=has_pxe_server,
                    has_dhcp_server=has_dhcp_server,
                    forward=forward)
            except IntegrityError:
                transaction.rollback()
        raise DevopsError("There is no network pool available for creating "
                          "the network {}".format(name))

    @classmethod
    def network_create(
        cls, name, environment=None, ip_network=None, pool=None,
        has_dhcp_server=True, has_pxe_server=False,
        forward='nat', reuse_network_pools=True
    ):
        """Create network

        :rtype : Network
        """
        if ip_network:
            return cls.objects.create(
                environment=environment,
                name=name,
                ip_network=ip_network,
                has_pxe_server=has_pxe_server,
                has_dhcp_server=has_dhcp_server,
                forward=forward
            )
        return cls._safe_create_network(
            environment=environment,
            forward=forward,
            has_dhcp_server=has_dhcp_server,
            has_pxe_server=has_pxe_server,
            name=name,
            pool=pool,
            reuse_network_pools=reuse_network_pools
        )

    @classmethod
    def create_networks(cls, environment, network_names=None,
                        has_dhcp=False, has_pxe=False, forward='nat',
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
            net = cls.network_create(name=name, environment=environment,
                                     has_dhcp_server=has_dhcp,
                                     has_pxe_server=has_pxe,
                                     forward=forward,
                                     pool=pool)
            networks.append(net)
        return networks


class DiskDevice(models.Model):
    class Meta(object):
        db_table = 'devops_diskdevice'

    node = models.ForeignKey('Node', null=False)
    volume = models.ForeignKey('Volume', null=True)
    device = choices('disk', 'cdrom')
    type = choices('file')
    bus = choices('virtio')
    target_dev = models.CharField(max_length=255, null=False)

    @classmethod
    def node_attach_volume(cls, node, volume, device='disk', type='file',
                           bus='virtio', target_dev=None):
        """Attach volume to node

        :rtype : DiskDevice
        """
        return cls.objects.create(
            device=device, type=type, bus=bus,
            target_dev=target_dev or node.next_disk_name(),
            volume=volume, node=node)


class Interface(models.Model):
    class Meta(object):
        db_table = 'devops_interface'

    network = models.ForeignKey('Network')
    node = models.ForeignKey('Node')
    mac_address = models.CharField(max_length=255, unique=True, null=False)
    type = models.CharField(max_length=255, null=False)
    model = choices('virtio', 'e1000', 'pcnet', 'rtl8139', 'ne2k_pci')

    @property
    def target_dev(self):
        return self.node.driver.node_get_interface_target_dev(
            self.node, self.mac_address)

    @property
    def addresses(self):
        return self.address_set.all()

    @staticmethod
    def interface_create(network, node, type='network',
                         mac_address=None, model='virtio',
                         interface_map=None):
        """Create interface

        :rtype : Interface
        """
        if interface_map is None:
            interface_map = {}
        interfaces = []

        def _create(mac_addr=None):
            interface = Interface.objects.create(
                network=network, node=node, type=type,
                mac_address=mac_addr or generate_mac(),
                model=model)
            Address.objects.create(ip_address=str(network.next_ip()),
                                   interface=interface)
            return interface

        if interface_map:
            if len(interface_map[network.name]) > 0:
                for _ in interface_map[network.name]:
                    interfaces.append(_create())
                return interfaces
        else:
            return _create(mac_address)


class Address(models.Model):
    class Meta(object):
        db_table = 'devops_address'

    interface = models.ForeignKey('Interface')
    ip_address = models.GenericIPAddressField()
