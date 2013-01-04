__author__ = 'vic'
from django.db import models

class EnvironmentManager(models.Manager):
    def create(self, name):
        return super(EnvironmentManager, self).create(name=name)

    def get_or_create(self, name):
        return super(EnvironmentManager, self).get_or_create(name=name)

class Environment(models.Model):
    name = models.CharField(max_length=255, unique=True, null=False)
    objects = EnvironmentManager()

class NetworkManager(models.Manager):
#    def create(self, name, dhcp_server=False, pxe=False, reserve_static=True, forward='nat'):
#        return super(NetworkManager, self).create(name=name)
    pass


class Network(models.Model):
    FORWARD_MODE_CHOOSES = (
        ('nat','nat'),
        ('route','route'),
        ('bridge','bridge'),
        ('private','private'),
        ('vepa','vepa'),
        ('passthrough','passthrough'),
        ('hostdev','hostdev'),
    )
    name = models.CharField(max_length=255, unique=True, null=False)
    uuid = models.CharField(max_length=255)
    has_dhcp_server = models.BooleanField(default=False, null=False)
    has_tftp_server = models.BooleanField(default=False, null=False)
    has_reserved_ips = models.BooleanField(default=True, null=False)
    tftp_root_dir = models.CharField(max_length=255, null=True)
    forward = models.CharField(max_length=10, null=False, choises=FORWARD_MODE_CHOOSES)
    ip_network = models.CharField(max_length=255, unique=True, null=True)
    environment = models.ForeignKey(Environment, null=True)
    objects = NetworkManager()

class NodeManager(models.Manager):
#    def create(self, name, cpu=1, memory=512, arch='x86_64', vnc=False,
#                 metadata=None):
#        super(NodeManager, self).create()
#if metadata is None:
#    self.metadata = {}
#else:
#self.metadata = metadata
#
#
    pass

class Node(models.Model):
    ARCHITECTURE_CHOOSES = (
        ('nat','nat'),
        ('route','route'),
        ('bridge','bridge'),
        ('private','private'),
        ('vepa','vepa'),
        ('passthrough','passthrough'),
        ('hostdev','hostdev'),
    )
    hypervisor = 'kvm'
    os_type = 'hvm'
    architecture = 'x86_64'
    boot = 'network'
    name = models.CharField(max_length=255, unique=True, null=False)
    uuid = models.CharField(max_length=255)
#    metadata = models.CharField(max_length=255, null=False, default='{}')
    vcpu = models.IntegerField(null=False, default=1)
    memory = models.IntegerField(null=False, default=1024)
    vnc = models.BooleanField(null=False, default=True)
    environment = models.ForeignKey(Environment, null=True)
    objects = NodeManager()
#    arch = models.CharField(max_length=10, null=False, choises)
#        self.interfaces = []
#        self.bridged_interfaces = []
#        self.disks = []
#        self.boot = []
#        self.cdrom = None
#        self.environment = None

class VolumeManager(models.Manager):
#    def __init__(self, capacity=None, path=None, format='qcow2', base_image=None):
    pass

    def upload(self, path):
        pass

class Volume(models.Model):
    name = models.CharField(max_length=255, unique=True, null=False)
    uuid = models.CharField(max_length=255)
    capacity = models.IntegerField(null=False)
    backing_store = models.ForeignKey('self', null=True)
    format = models.CharField(max_length=255, null=False)
    bus = models.CharField(max_length=255)
    objects = VolumeManager()
    environment = models.ForeignKey(Environment, null=True)

class InterfaceManager(models.Manager):
    pass

class Interface(models.Model):
    name = models.CharField(max_length=255, unique=True, null=False)
    uuid = models.CharField(max_length=255)
    mac_address = models.CharField(max_length=255, unique=True, null=False)
    network = models.ForeignKey(Network)
    node = models.ForeignKey(Node)
    type = models.CharField(max_length=255, null=False)
    target_dev = models.CharField(max_length=255, unique=True, null=False)

class AddressManager(models.Manager):
    pass

class Address(models.Model):
    ip_address = models.GenericIPAddressField()
    interface = models.ForeignKey(Interface)
    objects = AddressManager()
