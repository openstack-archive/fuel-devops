__author__ = 'vic'

from django.db import models

class EnvironmentManager(models.Manager):
    def create_environment(self, name):
        return super(EnvironmentManager, self).create(name=name)

    def get_or_create(self, name):
        return super(EnvironmentManager, self).get_or_create(name=name)

class NetworkManager(models.Manager):
    def create(self, name, dhcp_server=False, pxe=False, reserve_static=True, forward='nat'):
        return super(NetworkManager, self).create(name=name)
    pass

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
    pass

class AddressManager(models.Manager):
    pass
