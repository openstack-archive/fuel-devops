import ipaddr
from devops.helpers.helpers import generate_mac
from devops.helpers.network import IpNetworksPool

__author__ = 'vic'

from django.db import models


class Manager(models.Manager):

    pass

class EnvironmentManager(Manager):
    def create_environment(self, name):
        return super(EnvironmentManager, self).create(name=name)

    def list_environments(self):
        return self.values('name')

    def get_environment(self, name):
        return super(EnvironmentManager, self).get(name=name)


class NetworkManager(models.Manager):

    def create_network_pool(self, networks, prefix):
        return IpNetworksPool(networks=networks, prefix=prefix)

    def _get_default_pool(self):
        return self.create_network_pool(networks=[ipaddr.IPNetwork('10.0.0.0/16')], prefix=24)

    def create_network(
        self, environment, name, ip_network = None, pool=None, has_dhcp_server=False, has_pxe_server=False,
        forward='route'):
        _pool = pool or self._get_default_pool()
        return super(NetworkManager, self).create(environment=environment, name=name, ip_network=ip_network or _pool.next(), has_pxe_server=has_pxe_server, has_dhcp_server=has_dhcp_server, forward=forward)

class NodeManager(models.Manager):
    pass

class DiskDeviceManager(models.Manager):
    pass

class VolumeManager(models.Manager):
#    def __init__(self, capacity=None, path=None, format='qcow2', base_image=None):
    pass

    def upload(self, path):
        pass

class InterfaceManager(models.Manager):
    allocate_ip = True

    def _generate_mac(self):
        return generate_mac()

    def create_interface(self, network, node, type='network', target_dev=None, mac_address=None):
        interface = super(InterfaceManager, self).create(network=network, node=node, type=type, target_dev=target_dev, mac_address=mac_address or self._generate_mac())
        interface.add_address(str(network.next_ip()))
        return interface

class AddressManager(models.Manager):
    def create_address(self, ip_address, interface):
        super(AddressManager, self).create(ip_address=ip_address, interface=interface)
