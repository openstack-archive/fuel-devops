import json

from django.utils.importlib import import_module
from ipaddr import IPNetwork
from django.db import models

from devops.settings import DRIVER
from devops.helpers.helpers import SSHClient, _wait, _tcp_ping


def choices(*args, **kwargs):
    defaults = {'max_length': 255, 'null': False}
    defaults.update(kwargs)
    defaults.update(choices=double_tuple(*args))
    return models.CharField(**defaults)


def double_tuple(*args):
    dict = []
    for arg in args:
        dict.append((arg, arg))
    return tuple(dict)


class Environment(models.Model):
    name = models.CharField(max_length=255, unique=True, null=False)

    @property
    def volumes(self):
        return Volume.objects.filter(environment=self)

    @property
    def networks(self):
        return Network.objects.filter(environment=self)

    @property
    def nodes(self):
        return Node.objects.filter(environment=self)

    def node_by_name(self, name):
        return self.nodes.get(name=name, environment=self)

    def nodes_by_role(self, role):
        return self.nodes.filter(role=role, environment=self)

    def network_by_name(self, name):
        return self.networks.get(name=name, environment=self)

    def has_snapshot(self, name):
        return all(map(lambda x: x.has_snapshot(name), self.nodes))

    def define(self):
        for network in self.networks:
            network.define()
        for volume in self.volumes:
            volume.define()
        for node in self.nodes:
            node.define()

    def start(self, nodes=None):
        for network in self.networks:
            network.start()
        for node in nodes or self.nodes:
            node.start()

    def destroy(self, verbose=True):
        for node in self.nodes:
            node.destroy(verbose=verbose)

    def erase(self):
        for node in self.nodes:
            node.erase()
        for network in self.networks:
            network.erase()
        for volume in self.volumes:
            volume.erase()
        self.delete()

    def suspend(self, verbose=True):
        for node in self.nodes:
            node.suspend(verbose)

    def resume(self):
        for node in self.nodes:
            node.resume()

    def snapshot(self, name=None, description=None, force=False):
        for node in self.nodes:
            node.snapshot(name=name, description=description, force=force)

    def revert(self, name=None, destroy=True):
        if destroy:
            for node in self.nodes:
                node.destroy(verbose=False)
        for node in self.nodes:
            node.revert(name, destroy=False)


class ExternalModel(models.Model):
    _driver = None

    @classmethod
    def get_driver(cls):
        """
        :rtype : DevopsDriver
        """
        driver = import_module(DRIVER)
        cls._driver = cls._driver or driver.DevopsDriver()
        return cls._driver

    @property
    def driver(self):
        """
        :rtype : DevopsDriver
        """
        return self.get_driver()

    name = models.CharField(max_length=255, unique=False, null=False)
    uuid = models.CharField(max_length=255)
    environment = models.ForeignKey(Environment, null=True)

    class Meta:
        abstract = True
        unique_together = ('name', 'environment')

    @classmethod
    def get_allocated_networks(cls):
        return cls.get_driver().get_allocated_networks()

    @classmethod
    def allocate_network(cls, pool):
        while True:
            ip_network = pool.next()
            if not Network.objects.filter(ip_network=str(ip_network)).exists():
                return ip_network


class Network(ExternalModel):
    _iterhosts = None

    has_dhcp_server = models.BooleanField()
    has_pxe_server = models.BooleanField()
    has_reserved_ips = models.BooleanField(default=True)
    tftp_root_dir = models.CharField(max_length=255)
    forward = choices(
        'nat', 'route', 'bridge', 'private', 'vepa',
        'passthrough', 'hostdev', null=True)
    ip_network = models.CharField(max_length=255, unique=True)

    @property
    def interfaces(self):
        return Interface.objects.filter(network=self)

    @property
    def ip_pool_start(self):
        return IPNetwork(self.ip_network)[2]

    @property
    def ip_pool_end(self):
        return IPNetwork(self.ip_network)[-2]

    def next_ip(self):
        while True:
            self._iterhosts = self._iterhosts or IPNetwork(
                self.ip_network).iterhosts()
            ip = self._iterhosts.next()
            if ip < self.ip_pool_start or ip > self.ip_pool_end:
                continue
            if not Address.objects.filter(interface__network=self, ip_address=str(ip)).exists():
                return ip

    def bridge_name(self):
        return self.driver.network_bridge_name(self)

    def define(self):
        self.driver.network_define(self)
        self.save()

    def start(self):
        self.create(verbose=False)

    def create(self, verbose=True):
        if verbose or not self.driver.network_active(self):
            self.driver.network_create(self)

    def destroy(self):
        self.driver.network_destroy(self)

    def erase(self):
        self.remove(verbose=False)

    def remove(self, verbose=True):
        if verbose or self.uuid:
            if verbose or self.driver.network_exists(self):
                if self.driver.network_active(self):
                    self.driver.network_destroy(self)
                self.driver.network_undefine(self)
        self.delete()


class Node(ExternalModel):
    hypervisor = choices('kvm')
    os_type = choices('hvm')
    architecture = choices('x86_64', 'i686')
    boot = models.CharField(max_length=255, null=False, default=json.dumps([]))
    metadata = models.CharField(max_length=255, null=True)
    role = models.CharField(max_length=255, null=True)
    vcpu = models.PositiveSmallIntegerField(null=False, default=1)
    memory = models.IntegerField(null=False, default=1024)
    has_vnc = models.BooleanField(null=False, default=True)

    def next_disk_name(self):
        disk_names = ('sd' + c for c in list('abcdefghijklmnopqrstuvwxyz'))
        while True:
            disk_name = disk_names.next()
            if not self.disk_devices.filter(target_dev=disk_name).exists():
                return disk_name

    def get_vnc_port(self):
        return self.driver.node_get_vnc_port(node=self)

    @property
    def disk_devices(self):
        return DiskDevice.objects.filter(node=self)

    @property
    def interfaces(self):
        return Interface.objects.filter(node=self).order_by('id')

    def interface_by_name(self, name):
        self.interfaces.filter(name=name)

    def get_ip_address_by_network_name(self, name):
        return Address.objects.get(
            interface__network__name=name, interface__node=self).ip_address

    def remote(self, network_name, login, password=None, private_keys=None):
        """
        :rtype : SSHClient
        """
        return SSHClient(
            self.get_ip_address_by_network_name(network_name),
            username=login,
            password=password, private_keys=private_keys)

    def send_keys(self, keys):
        self.driver.node_send_keys(self, keys)

    def await(self, network_name, timeout=120):
        _wait(
            lambda: _tcp_ping(
                self.get_ip_address_by_network_name(network_name), 22),
            timeout=timeout)

    def define(self):
        self.driver.node_define(self)
        self.save()

    def start(self):
        self.create(verbose=False)

    def create(self, verbose=True):
        if verbose or not self.driver.node_active(self):
            self.driver.node_create(self)

    def destroy(self, verbose=True):
        if verbose or self.driver.node_active(self):
            self.driver.node_destroy(self)

    def erase(self):
        self.remove(verbose=False)

    def remove(self, verbose=True):
        if verbose or self.uuid:
            if verbose or self.driver.node_exists(self):
                self.destroy(verbose=False)
                self.driver.node_delete_all_snapshots(node=self)
                self.driver.node_undefine(self)
        self.delete()

    def suspend(self, verbose=True):
        if verbose or self.driver.node_active(self):
            self.driver.node_suspend(self)

    def resume(self):
        self.driver.node_resume(self)

    def has_snapshot(self, name):
        return self.driver.node_snapshot_exists(node=self, name=name)

    def snapshot(self, name=None, force=False, description=None):
        if force and self.has_snapshot(name):
            self.driver.node_delete_snapshot(node=self, name=name)
        self.driver.node_create_snapshot(
            node=self, name=name, description=description)

    def revert(self, name=None, destroy=True):
        if destroy:
            self.destroy(verbose=False)
        self.driver.node_revert_snapshot(node=self, name=name)


class Volume(ExternalModel):
    capacity = models.BigIntegerField(null=False)
    backing_store = models.ForeignKey('self', null=True)
    format = models.CharField(max_length=255, null=False)

    def define(self):
        self.driver.volume_define(self)
        self.save()

    def erase(self):
        self.remove(verbose=False)

    def remove(self, verbose=True):
        if verbose or self.uuid:
            if verbose or self.driver.volume_exists(self):
                self.driver.volume_delete(self)
        self.delete()

    def get_capacity(self):
        return self.driver.volume_capacity(self)

    def get_format(self):
        return self.driver.volume_format(self)

    def get_path(self):
        return self.driver.volume_path(self)

    def fill_from_exist(self):
        self.capacity = self.get_capacity()
        self.format = self.get_format()

    def upload(self, path):
        self.driver.volume_upload(self, path)


class DiskDevice(models.Model):
    device = choices('disk', 'cdrom')
    type = choices('file')
    bus = choices('virtio')
    target_dev = models.CharField(max_length=255, null=False)
    node = models.ForeignKey(Node, null=False)
    volume = models.ForeignKey(Volume, null=True)


class Interface(models.Model):
    mac_address = models.CharField(max_length=255, unique=True, null=False)
    network = models.ForeignKey(Network)
    node = models.ForeignKey(Node)
    type = models.CharField(max_length=255, null=False)
    model = choices('virtio')

    @property
    def target_dev(self):
        return self.node.driver.node_get_interface_target_dev(
            self.node, self.mac_address)

    @property
    def addresses(self):
        return Address.objects.filter(interface=self)

    def add_address(self, address):
        Address.objects.create(ip_address=address, interface=self)


class Address(models.Model):
    ip_address = models.GenericIPAddressField()
    interface = models.ForeignKey(Interface)
