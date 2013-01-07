from ipaddr import IPNetwork
from devops.managers import EnvironmentManager, NodeManager, DiskDeviceManager, VolumeManager, AddressManager, NetworkManager

from django.db import models

def choices(*args, **kwargs):
    defaults = {'max_length':255, 'null':False}
    defaults.update(kwargs)
    defaults.update(choices=double_tuple(*args))
    return models.CharField(**defaults)

def double_tuple(*args):
    dict = []
    for arg in args:
        dict.append((arg,arg))
    return tuple(dict)

class ExternalModel(models.Model):
    name = models.CharField(max_length=255, unique=True, null=False)
    uuid = models.CharField(max_length=255)

class Environment(models.Model):
    name = models.CharField(max_length=255, unique=True, null=False)
    objects = EnvironmentManager()

    @property
    def nodes(self):
        return Node.objects.filter(environment=self)

    @property
    def networks(self):
        return Network.objects.filter(environment=self)

    def node_by_name(self, name):
        self.nodes.filter(name=name)

    def nodes_by_role(self, role):
        self.nodes.filter(role=role)

    def network_by_name(self, name):
        self.networks.filter(name=name)

class Network(ExternalModel):
    has_dhcp_server = models.BooleanField()
    has_pxe_server = models.BooleanField()
    has_reserved_ips = models.BooleanField(default=True)
    tftp_root_dir = models.CharField(max_length=255)
    forward = choices('nat', 'route', 'bridge', 'private', 'vepa', 'passthrough', 'hostdev')
    ip_network = models.CharField(max_length=255, unique=True)
    environment = models.ForeignKey(Environment, null=True)
    objects = NetworkManager()

    @property
    def interfaces(self):
        return Interface.objects.filter(network=self)

    @property
    def dhcp_start(self):
        return IPNetwork(self.ip_network).iterhosts

class Node(ExternalModel):
    hypervisor = choices('kvm')
    os_type = choices('hvm')
    architecture = choices('x86_64','i686')
    boot = ['network', 'cdrom', 'hd']
    metadata = models.CharField(max_length=255, null=True)
    role = models.CharField(max_length=255, null=True)
    vcpu = models.PositiveSmallIntegerField(null=False, default=1)
    memory = models.IntegerField(null=False, default=1024)
    has_vnc = models.BooleanField(null=False, default=True)
    environment = models.ForeignKey(Environment, null=True)
    objects = NodeManager()

    @property
    def disk_devices(self):
        return DiskDevice.objects.filter(node=self)

    @property
    def interfaces(self):
        return Interface.objects.filter(node=self)

class DiskDevice(models.Model):
    device = choices('disk', 'cdrom')
    type = choices('file')
    bus = choices('virtio')
    target_dev =  models.CharField(max_length=255, null=False)
    objects = DiskDeviceManager()

class Volume(ExternalModel):
    capacity = models.IntegerField(null=False)
    backing_store = models.ForeignKey('self', null=True)
    format = models.CharField(max_length=255, null=False)
    objects = VolumeManager()
    environment = models.ForeignKey(Environment, null=True)

class Interface(ExternalModel):
    mac_address = models.CharField(max_length=255, unique=True, null=False)
    network = models.ForeignKey(Network)
    node = models.ForeignKey(Node)
    type = models.CharField(max_length=255, null=False)
    target_dev = models.CharField(max_length=255, unique=True, null=False)

class Address(models.Model):
    ip_address = models.GenericIPAddressField()
    interface = models.ForeignKey(Interface)
    objects = AddressManager()
