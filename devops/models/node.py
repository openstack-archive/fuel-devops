#    Copyright 2013 - 2016 Mirantis, Inc.
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

import functools

from django.db import models
from django.utils.functional import cached_property
import six

from devops.error import DevopsObjNotFound
from devops.helpers.helpers import tcp_ping_
from devops.helpers.helpers import wait_pass
from devops.helpers import loader
from devops.helpers.ssh_client import SSHClient
from devops import logger
from devops.models.base import BaseModel
from devops.models.base import ParamedModel
from devops.models.base import ParamedModelType
from devops.models.base import ParamField
from devops.models.network import NetworkConfig
from devops.models.volume import Volume


class ExtendableNodeType(ParamedModelType):
    """Atomatically installs hooks on Node subclasses

    This class dynamically installs hooks for specified methods,
    to invoke pre_* and post_* methods from node role extensions (if such
    methods exist).

    The following methods with custom logic can be added to the node
    role extensions:

    def pre_define(self):
    def post_define(self):
    def pre_start(self):
    def post_start(self):
    def pre_destroy(self):
    def post_destroy(self):
    def pre_remove(self):
    def post_remove(self):

    For example, if some method should be called *before* each invocation of
    Node.start() for the role 'fuel_slave', then:
    - add a pre_start(self) method to
      the devops.models.node_ext.fuel_slave module
    - Every time when Node.start() invoked for the role 'fuel_slave',
      execution will be performed like the following (simplified
      explanation):

    .. code-block::

        def hook(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                Node.ext.pre_start()  # <- method that was added
                result = func(*args, **kwargs)
                # Node.ext.post_start()  # post_start() wasn't added to the
                                         # node role extension, so in this
                                         # case will be called 'dumb' method
                                         # that do nothing.
                return result
            return wrapper

        @hook  # This hook is dynamically installed for each instance of Node
               # depending on the role.
        def start(self):
           ...
"""

    METHOD_NAMES = ('define', 'start', 'destroy', 'remove')

    def __new__(cls, name, bases, attrs):
        super_new = super(ExtendableNodeType, cls).__new__

        # skip if not a Node subclass
        if 'Node' not in [c.__name__ for c in bases]:
            return super_new(cls, name, bases, attrs)

        # add method to subclass if there is no such
        for attr_name in cls.METHOD_NAMES:
            if attr_name in attrs:
                continue
            # if there is no method in subclass
            # then we can't install hooks
            attrs[attr_name] = cls._create_method(attr_name)

        # install ext hooks on Node subclasses
        for attr_name in attrs:
            if attr_name not in cls.METHOD_NAMES:
                continue
            attrs[attr_name] = cls._install_ext_hook(attrs[attr_name])

        return super_new(cls, name, bases, attrs)

    @staticmethod
    def _install_ext_hook(node_method):
        """Installs pre/post hooks on Node method"""

        @functools.wraps(node_method)
        def wrapper(*args, **kwargs):
            node = args[0]
            name = node_method.__name__

            pre_method = getattr(node.ext, 'pre_{}'.format(name), None)
            post_method = getattr(node.ext, 'post_{}'.format(name), None)

            if pre_method is not None:
                pre_method()

            result = node_method(*args, **kwargs)

            if post_method is not None:
                post_method()

            return result

        return wrapper

    @staticmethod
    def _create_method(name):
        """Creates a simple method which just calls super method"""
        def method(self, *args, **kwargs):
            return getattr(super(self.__class__, self), name)(*args, **kwargs)
        method.__name__ = name
        return method


class Node(six.with_metaclass(ExtendableNodeType, ParamedModel, BaseModel)):
    class Meta(object):
        unique_together = ('name', 'group')
        db_table = 'devops_node'
        app_label = 'devops'

    group = models.ForeignKey('Group', null=True)
    name = models.CharField(max_length=255, unique=False, null=False)
    role = models.CharField(max_length=255, null=True)

    kernel_cmd = ParamField()
    ssh_port = ParamField(default=22)
    bootstrap_timeout = ParamField(default=600)
    deploy_timeout = ParamField(default=3600)
    deploy_check_cmd = ParamField()

    @property
    def driver(self):
        drv = self.group.driver

        # LEGACY (fuel-qa compatibility requires), TO REMOVE
        def node_active(node):
            return node.is_active()
        drv.node_active = node_active

        return drv

    @cached_property
    def ext(self):
        try:
            ExtCls = loader.load_class(
                'devops.models.node_ext.{ext_name}:NodeExtension'
                ''.format(ext_name=self.role or 'default'))
            return ExtCls(node=self)
        except ImportError:
            logger.debug('NodeExtension is not found for role: {!r}'
                         ''.format(self.role))
            return None

    def define(self, *args, **kwargs):
        for iface in self.interfaces:
            iface.define()
        self.save()

    def start(self, *args, **kwargs):
        pass

    def destroy(self, *args, **kwargs):
        self._close_remotes()

    def erase(self, *args, **kwargs):
        self.remove()

    def remove(self, *args, **kwargs):
        self._close_remotes()
        self.erase_volumes()
        for iface in self.interfaces:
            iface.remove()
        self.delete()

    def suspend(self, *args, **kwargs):
        self._close_remotes()

    def resume(self, *args, **kwargs):
        pass

    def snapshot(self, *args, **kwargs):
        pass

    def revert(self, *args, **kwargs):
        self._close_remotes()

    # for fuel-qa compatibility
    def has_snapshot(self, *args, **kwargs):
        return True

    def reboot(self):
        pass

    def shutdown(self):
        self._close_remotes()

    def reset(self):
        pass

    def get_vnc_port(self):
        return None

    # for fuel-qa compatibility
    def get_snapshots(self):
        """Return full snapshots objects"""
        return []

    @property
    def disk_devices(self):
        return self.diskdevice_set.all()

    @property
    def interfaces(self):
        return self.interface_set.order_by('id')

    @property
    def network_configs(self):
        return self.networkconfig_set.all()

    # LEGACY, for fuel-qa compatibility
    @property
    def is_admin(self):
        return 'master' in self.role

    # LEGACY, for fuel-qa compatibility
    @property
    def is_slave(self):
        return self.role == 'fuel_slave'

    def next_disk_name(self):
        disk_names = ('sd' + c for c in list('abcdefghijklmnopqrstuvwxyz'))
        for disk_name in disk_names:
            if not self.disk_devices.filter(target_dev=disk_name).exists():
                return disk_name

    # TODO(astudenov): LEGACY, TO REMOVE
    def interface_by_network_name(self, network_name):
        logger.warning('interface_by_network_name is deprecated in favor of '
                       'get_interface_by_network_name')
        raise DeprecationWarning(
            "'Node.interface_by_network_name' is deprecated. "
            "Use 'Node.get_interface_by_network_name' instead.")

    def get_interface_by_network_name(self, network_name):
        return self.interface_set.get(
            l2_network_device__name=network_name)

    def get_interface_by_nailgun_network_name(self, name):
        for net_conf in self.networkconfig_set.all():
            if name in net_conf.networks:
                label = net_conf.label
                break
        else:
            return None
        return self.interface_set.get(label=label)

    def get_ip_address_by_network_name(self, name, interface=None):
        interface = interface or self.interface_set.filter(
            l2_network_device__name=name).order_by('id')[0]
        return interface.address_set.get(interface=interface).ip_address

    def get_ip_address_by_nailgun_network_name(self, name):
        interface = self.get_interface_by_nailgun_network_name(name)
        return interface.address_set.first().ip_address

    def remote(
            self, network_name, login=None, password=None, private_keys=None,
            auth=None):
        """Create SSH-connection to the network

        :rtype : SSHClient
        """
        return SSHClient(
            self.get_ip_address_by_network_name(network_name),
            username=login,
            password=password, private_keys=private_keys, auth=auth)

    def _close_remotes(self):
        """Call close cached ssh connections for current node"""
        for network_name in {'admin', 'public', 'internal'}:
            try:
                SSHClient.close_connections(
                    hostname=self.get_ip_address_by_network_name(network_name))
            except BaseException:
                logger.debug(
                    '{0}._close_remotes for {1} failed'.format(
                        self.name, network_name))

    def await(self, network_name, timeout=120, by_port=22):
        wait_pass(
            lambda: tcp_ping_(
                self.get_ip_address_by_network_name(network_name), by_port),
            timeout=timeout)

    # NEW
    def add_interfaces(self, interfaces):
        for interface in interfaces:
            label = interface['label']
            l2_network_device_name = interface.get('l2_network_device')
            interface_model = interface.get('interface_model', 'virtio')
            mac_address = interface.get('mac_address')
            self.add_interface(
                label=label,
                l2_network_device_name=l2_network_device_name,
                mac_address=mac_address,
                interface_model=interface_model)

    # NEW
    def add_interface(self, label, l2_network_device_name,
                      interface_model, mac_address=None):
        if l2_network_device_name:
            env = self.group.environment
            l2_network_device = env.get_env_l2_network_device(
                name=l2_network_device_name)
        else:
            l2_network_device = None

        cls = self.driver.get_model_class('Interface')
        return cls.interface_create(
            node=self,
            label=label,
            l2_network_device=l2_network_device,
            mac_address=mac_address,
            model=interface_model,
        )

    # NEW
    def add_network_configs(self, network_configs):
        for label, data in network_configs.items():
            self.add_network_config(
                label=label,
                networks=data.get('networks', []),
                aggregation=data.get('aggregation'),
                parents=data.get('parents', []),
            )

    # NEW
    def add_network_config(self, label, networks=None, aggregation=None,
                           parents=None):
        if networks is None:
            networks = []
        if parents is None:
            parents = []
        NetworkConfig.objects.create(
            node=self,
            label=label,
            networks=networks,
            aggregation=aggregation,
            parents=parents,
        )

    # NEW
    def add_volumes(self, volumes):
        for vol_params in volumes:
            self.add_volume(
                **vol_params
            )

    # NEW
    def add_volume(self, name, device='disk', bus='virtio', **params):
        cls = self.driver.get_model_class('Volume')
        volume = cls.objects.create(
            node=self,
            name=name,
            **params
        )
        # TODO(astudenov): make a separete section in template for disk devices
        self.attach_volume(
            volume=volume,
            device=device,
            bus=bus,
        )
        return volume

    # NEW
    def attach_volume(self, volume, device='disk', type='file',
                      bus='virtio', target_dev=None):
        """Attach volume to node

        :rtype : DiskDevice
        """
        cls = self.driver.get_model_class('DiskDevice')
        return cls.objects.create(
            device=device, type=type, bus=bus,
            target_dev=target_dev or self.next_disk_name(),
            volume=volume, node=self)

    # NEW
    def get_volume(self, **kwargs):
        try:
            return self.volume_set.get(**kwargs)
        except Volume.DoesNotExist:
            raise DevopsObjNotFound(Volume, **kwargs)

    # NEW
    def get_volumes(self, **kwargs):
        return self.volume_set.filter(**kwargs).order_by('id')

    # NEW
    def erase_volumes(self):
        for volume in self.get_volumes():
            volume.erase()
