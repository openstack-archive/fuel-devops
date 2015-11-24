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

# from django.conf import settings
from django.db import models

from devops.helpers.helpers import _tcp_ping
from devops.helpers.helpers import _wait
from devops.helpers.helpers import _get_file_size
from devops.helpers.helpers import SSHClient
# from devops.models.base import choices
from devops.models.base import BaseModel
from devops.models.base import ParamedModel
from devops.models.network import Interface
from devops.models.network import NetworkConfig
# from devops.models.volume import Volume
from devops.models.volume import DiskDevice


class Node(ParamedModel, BaseModel):
    class Meta(object):
        unique_together = ('name', 'group')
        db_table = 'devops_node'
        app_label = 'devops'

    group = models.ForeignKey('Group', null=True)
    name = models.CharField(max_length=255, unique=False, null=False)
    role = models.CharField(max_length=255, null=True)

    @property
    def driver(self):
        self.group.driver

    def define(self):
        pass

    def start(self):
        pass

    def destroy(self):
        pass

    def erase(self):
        pass

    @property
    def disk_devices(self):
        return self.diskdevice_set.all()

    @property
    def interfaces(self):
        return self.interface_set.order_by('id')

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_slave(self):
        return self.role == 'slave'

    def next_disk_name(self):
        disk_names = ('sd' + c for c in list('abcdefghijklmnopqrstuvwxyz'))
        while True:
            disk_name = disk_names.next()
            if not self.disk_devices.filter(target_dev=disk_name).exists():
                return disk_name

    def interface_by_network_name(self, network_name):
        return self.interface_set.filter(
            l2_network_device__name=network_name)

    def get_ip_address_by_network_name(self, name, interface=None):
        interface = interface or self.interface_set.filter(
            l2_network_device__name=name).order_by('id')[0]
        return interface.address_set.get(interface=interface).ip_address

    def remote(self, network_name, login, password=None, private_keys=None):
        """Create SSH-connection to the network

        :rtype : SSHClient
        """
        return SSHClient(
            self.get_ip_address_by_network_name(network_name),
            username=login,
            password=password, private_keys=private_keys)

    def await(self, network_name, timeout=120, by_port=22):
        _wait(
            lambda: _tcp_ping(
                self.get_ip_address_by_network_name(network_name), by_port),
            timeout=timeout)

    @property
    def should_enable_boot_menu(self):
        """Method of node to decide if it should enable boot menu.

        Boot menu is necessary in cases when boot device is other than first
        network or disk on kvm. Such cases are: master node usb boot and slave
        node boot via network not on eth0.
        Depending on return value of that method libvirt xml builder should
        add to domain xml element bootmenu with attributes enabled=yes and
        timeout = 3000.

        :returns: Boolean
        """
        return (self.is_admin and self.disk_devices.filter(bus='usb')) or \
            (self.is_slave and not self.pxe_boot_interface_is_eth0)

    @property
    def on_second_admin_network(self):
        """Method to get information about node if it is on second admin net.

        :returns: Boolean
        """
        if self.is_admin:
            return True
        if settings.MULTIPLE_NETWORKS:
            # TODO(akostrikov) 'admin2' as environment property or constant.
            network = self.group.get_network(name='admin2')
        else:
            network = None

        if network:
            return self.interface_set.filter(network_id=network.id,
                                             node_id=self.id).exists()
        else:
            return False

    @property
    def pxe_boot_interface_is_eth0(self):
        """This method checks if admin interface is on eth0.

        It assumes that we are assigning interfaces with 'for node' in
        self.group.create_interfaces in which we run on all networks with
        'for network in networks: Interface.interface_create'.
        Which is called in
        'environment.describe_empty_node(name, networks_to_describe, volumes)'.
        And networks in 'devops.environment.describe_environment' are got from:
        in usual case 'interfaces = settings.INTERFACE_ORDER'
        or with bonding 'settings.BONDING_INTERFACES.keys()'
        Later interfaces are used with 'self.interface_set.order_by("id")' in
        _build_interface_device.
        So in current state of devops interfaces are ordered as networks in
        settings.INTERFACE_ORDER or settings.BONDING_INTERFACES.keys().
        Based on that information we decide if admin net for that node group
        on that node is on first interface.
        That method does not apply to admin node because it does not matter
        from which interface to provide pxe.

        :returns: Boolean
        """
        first_net_name = self.group.get_networks().order_by('id')[0].name

        if self.is_admin:
            return False
        elif self.on_second_admin_network:
            return first_net_name == 'admin2'
        else:
            return first_net_name == 'admin'

    # NEW
    def add_interfaces(self, interfaces):
        for interface in interfaces:
            label = interface['label']
            l2_network_device_name = interface.get('l2_network_device')
            self.add_interface(
                label=label,
                l2_network_device_name=l2_network_device_name)

    # NEW
    def add_interface(self, label, l2_network_device_name):
        l2_network_device = self.group.get_l2_network_device(
            name=l2_network_device_name)

        Interface.interface_create(
            node=self,
            l2_network_device=l2_network_device,
        )

    # NEW
    def add_network_configs(self, network_configs):
        for label, data in network_configs.iteritems():
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
        for volume in volumes:
            self.add_volume(
                name=volume['name'],
                capacity=volume.get('capacity'),
                device=volume['device'],
                bus=volume['bus'],
                format=volume['format'],
                source_image=volume.get('source_image'),
            )

    # NEW
    def add_volume(self, name, capacity=50 * 1024 ** 3,
                   device='disk', bus='virtio', format='qcow2',
                   source_image=None):
        if source_image:
            capacity = _get_file_size(source_image)

        cls = self.driver.get_model_class('Volume')
        volume = cls.objects.create(
            name=name,
            capacity=capacity,
            group=self.group,
            format=format)
        return DiskDevice.node_attach_volume(
            node=self,
            volume=volume,
            device=device,
            bus=bus)

    # TO REMOVE
    def attach_disks(self,
                     disknames_capacity=None,
                     format='qcow2', device='disk', bus='virtio',
                     force_define=False):
        """Attach several disks to node


        param: disknames_capacity: Dict
        param: format: String
        param: device: String
        param: bus: String
        param: force_define: Bool
            :rtype : None
        """
        if disknames_capacity is None:
            disknames_capacity = {
                'system': 50 * 1024 ** 3,
                'swift': 50 * 1024 ** 3,
                'cinder': 50 * 1024 ** 3,
            }

        for diskname, capacity in disknames_capacity.iteritems():
            self.attach_disk(name=diskname,
                             capacity=capacity,
                             force_define=force_define)

    # TO REMOVE
    def attach_disk(self, name, capacity, format='qcow2',
                    device='disk', bus='virtio', force_define=False):
        """Attach disk to node


        param: disknames_capacity: Dict
        param: format: String
        param: device: String
        param: bus: String
        param: force_define: Bool
            :rtype : DiskDevice
        """
        vol_name = "%s-%s" % (self.name, name)
        disk = self.group.add_empty_volume(node=self,
                                           name=vol_name,
                                           capacity=capacity,
                                           device=device,
                                           bus=bus)
        if force_define:
            disk.volume.define()
        return disk
