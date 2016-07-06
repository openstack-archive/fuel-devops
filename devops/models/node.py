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

from __future__ import print_function

import json

from django.conf import settings
from django.db import models

from devops.error import DevopsError
from devops.helpers.helpers import SSHClient
from devops.helpers.helpers import tcp_ping_
from devops.helpers.helpers import wait_pass
from devops import logger
from devops.models.base import choices
from devops.models.base import DriverModel
from devops.models.volume import Volume


class NodeManager(models.Manager):
    def create(self, *args, **kwargs):
        Node.node_create(*args, **kwargs)

    def all(self, *args, **kwargs):
        Node.objects.all()


class Node(DriverModel):
    class Meta(object):
        unique_together = ('name', 'environment')
        db_table = 'devops_node'

    environment = models.ForeignKey('Environment', null=True)
    name = models.CharField(max_length=255, unique=False, null=False)
    uuid = models.CharField(max_length=255)
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
            disk_name = next(disk_names)
            if not self.disk_devices.filter(target_dev=disk_name).exists():
                return disk_name

    def get_vnc_port(self):
        return self.driver.node_get_vnc_port(node=self)

    @property
    def disk_devices(self):
        return self.diskdevice_set.all()

    @property
    def interfaces(self):
        return self.interface_set.order_by('id')

    @property
    def vnc_password(self):
        return settings.VNC_PASSWORD

    @property
    def is_admin(self):
        return self.role == 'fuel_master'

    @property
    def is_slave(self):
        return self.role == 'fuel_slave'

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
            network = self.environment.get_network(name='admin2')
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
        self.environment.create_interfaces in which we run on all networks with
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
        first_net_name = self.environment.get_networks().order_by('id')[0].name

        if self.is_admin:
            return False
        elif self.on_second_admin_network:
            return first_net_name == 'admin2'
        else:
            return first_net_name == 'admin'

    def interface_by_network_name(self, network_name):
        return self.interface_set.filter(
            network__name=network_name)

    def get_ip_address_by_network_name(self, name, interface=None):
        interface = interface or self.interface_set.filter(
            network__name=name).order_by('id')[0]
        return interface.address_set.get(interface=interface).ip_address

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

    def send_keys(self, keys):
        self.driver.node_send_keys(self, keys)

    def await(self, network_name, timeout=120, by_port=22):
        wait_pass(
            lambda: tcp_ping_(
                self.get_ip_address_by_network_name(network_name), by_port),
            timeout=timeout)

    def define(self):
        """Define node and interface filter"""
        if settings.ENABLE_LIBVIRT_NWFILTERS:
            for iface in self.interfaces:
                iface.define_filter()
        self.driver.node_define(self)
        self.save()

    def start(self):
        self.create(verbose=False)

    def create(self, verbose=False):
        if verbose or not self.driver.node_active(self):
            self.driver.node_create(self)

    def destroy(self, verbose=False):
        SSHClient.close_connections()
        if verbose or self.driver.node_active(self):
            self.driver.node_destroy(self)

    def erase(self):
        self.remove(verbose=False)

    def remove(self, verbose=False):
        """Remove node and filters for interfaces"""
        if verbose or self.uuid:
            if verbose or self.driver.node_exists(self):
                self.destroy(verbose=False)
                self.driver.node_undefine(self, undefine_snapshots=True)
                for iface in self.interfaces:
                    iface.undefine_filter()
        self.delete()

    def suspend(self, verbose=False):
        SSHClient.close_connections()
        if verbose or self.driver.node_active(self):
            self.driver.node_suspend(self)

    def resume(self, verbose=False):
        if verbose or self.driver.node_active(self):
            self.driver.node_resume(self)

    def reset(self):
        self.driver.node_reset(self)

    def has_snapshot(self, name):
        return self.driver.node_snapshot_exists(node=self, name=name)

    def snapshot_create_volume(self, name):
        """Create volume child for snapshot"""
        for disk in self.disk_devices:
            if disk.device == 'disk':

                # Find main disk name, it is used for external disk
                back_vol_name = disk.volume.name
                back_count = 0
                disk_test = disk.volume.backing_store
                while disk_test is not None:
                    back_count += 1
                    back_vol_name = disk_test.name
                    disk_test = disk_test.backing_store
                    if back_count > 500:
                        raise DevopsError(
                            "More then 500 snapshots in chain for {0}.{1}"
                            .format(back_vol_name, name))

                # Create new volume for snapshot
                vol_child = Volume.volume_create_child(
                    name='{0}.{1}'.format(back_vol_name, name),
                    backing_store=disk.volume,
                    environment=self.environment
                )
                vol_child.define()

                # update disk node to new snapshot
                disk.volume = vol_child
                disk.save()

    def snapshot(self, name=None, force=False, description=None,
                 disk_only=False, external=False):
        if self.has_snapshot(name):
            if force:
                self.driver.node_delete_snapshot(node=self, name=name)
            else:
                raise DevopsError("Snapshot with name {0} already exists"
                                  .format(name))

        if external:
            if self.driver.get_libvirt_version() < 1002012:
                raise DevopsError(
                    "For external snapshots we need libvirtd >= 1.2.12")

            # create new volume which will be used as
            # disk for snapshot changes
            self.snapshot_create_volume(name)
        self.driver.node_create_snapshot(
            node=self, name=name, description=description, disk_only=disk_only,
            external=external)

    def _update_disks_from_snapshot(self, name):
        """Update actual node disks volumes to disks from snapshot

           This method change disks attached to actual node to
           disks used in snapshot. This is required to save correct
           state of node disks. We use node disks as a backend when
           new snapshots are created.
        """
        snapshot = self.driver.node_get_snapshot(self, name)
        for snap_disk, snap_disk_file in snapshot.disks.items():
            for disk in self.disk_devices:
                if snap_disk == disk.target_dev:
                    if snapshot.children_num == 0:
                        disk.volume = Volume.objects.get(uuid=snap_disk_file)
                    else:
                        disk.volume = Volume.objects.get(
                            uuid=snap_disk_file).backing_store
                    disk.save()

    def revert(self, name=None, destroy=True):
        """Method to revert node in state from snapshot

           For external snapshots in libvirt we use restore function.
           After reverting in this way we get situation when node is connected
           to original volume disk, without snapshot point. To solve this
           problem we need to switch it to correct volume.

           In case of usage external snapshots we clean snapshot disk when
           revert to snapshot without childs and create new snapshot point
           when reverting to snapshots with childs.
        """
        SSHClient.close_connections()
        if destroy:
            self.destroy(verbose=False)
        if self.has_snapshot(name):
            snapshot = self.driver.node_get_snapshot(self, name)
            if snapshot.get_type == 'external':
                self.destroy()
                if snapshot.children_num == 0:
                    logger.info("Reuse last snapshot")

                    # Update current node disks
                    self._update_disks_from_snapshot(name)

                    # Recreate volumes for snapshot and reuse it.
                    self.driver.node_revert_snapshot_recreate_disks(self, name)

                    # Revert snapshot
                    self.driver.node_revert_snapshot(node=self, name=name)
                else:
                    # Looking for last reverted snapshot without children
                    # or create new and start next snapshot chain
                    revert_name = name + '-revert'
                    revert_count = 0
                    create_new = True

                    while self.has_snapshot(revert_name):
                        # Check wheter revert snapshot has children
                        snapshot_revert = self.driver.node_get_snapshot(
                            self, revert_name)
                        if snapshot_revert.children_num == 0:
                            logger.info(
                                "Revert snapshot exists, clean and reuse it")

                            # Update current node disks
                            self._update_disks_from_snapshot(revert_name)

                            # Recreate volumes
                            self.driver.node_revert_snapshot_recreate_disks(
                                self, revert_name)

                            # Revert snapshot
                            self.driver.node_revert_snapshot(
                                node=self, name=revert_name)
                            create_new = False
                            break
                        else:
                            revert_name = name + '-revert' + str(revert_count)
                            revert_count += 1

                    if create_new:
                        logger.info("Create new revert snapshot")

                        # Update current node disks
                        self._update_disks_from_snapshot(name)

                        # Revert snapshot
                        self.driver.node_revert_snapshot(node=self, name=name)

                        # Create new snapshot
                        self.snapshot(name=revert_name, external=True)
            else:
                self.driver.node_revert_snapshot(node=self, name=name)
        else:
            print('Domain snapshot for {0} node not found: no domain '
                  'snapshot with matching'
                  ' name {1}'.format(self.name, name))
        for iface in self.interfaces:
            if iface.is_blocked:
                logger.info("Interface({}) in {} network has "
                            "been unblocked".format(iface.mac_address,
                                                    iface.network.name))
                iface.unblock()

    def get_snapshots(self):
        """Return full snapshots objects"""
        return self.driver.node_get_snapshots(node=self)

    def erase_snapshot(self, name):
        if self.has_snapshot(name):
            snapshot = self.driver.node_get_snapshot(self, name)
            if snapshot.get_type == 'external':
                if snapshot.children_num == 0:
                    self.driver.node_delete_snapshot(node=self, name=name)
                    for disk in self.disk_devices:
                        if disk.device == 'disk':
                            snap_disk = disk.volume
                            # update disk on node
                            disk.volume = disk.volume.backing_store
                            disk.save()
                            snap_disk.remove()
                else:
                    logger.error(
                        "Cannot delete external snapshots with children")
            else:
                self.driver.node_delete_snapshot(node=self, name=name)

    def set_vcpu(self, vcpu):
        """Set vcpu count on node

        param: vcpu: Integer
            :rtype : None
        """
        if vcpu is not None and vcpu != self.vcpu:
            self.vcpu = vcpu
            self.driver.node_set_vcpu(node=self, vcpu=vcpu)
            self.save()

    def set_memory(self, memory):
        """Set memory size on node

        param: memory: Integer
            :rtype : None
        """
        if memory is not None and memory != self.memory:
            self.memory = memory
            self.driver.node_set_memory(node=self, memory=memory * 1024)
            self.save()

    def set_boot(self, boot):
        """Set boot order on node

        :type boot: list
        :rtype: None
        """
        self.driver.node_set_boot(node=self, boot=boot)
        self.boot = json.dumps(boot)
        self.save()

    def close_tray(self):
        """Closes tray for all cdrom devices

        :rtype: None
        """
        self.driver.node_close_tray(self)

    def attach_to_networks(self, network_names=None):
        """Attache node to several networks


        param: network_names: List
            :rtype : None
        """
        if network_names is None:
            network_names = settings.DEFAULT_INTERFACE_ORDER.split(',')
        networks = [
            self.environment.get_network(name=n) for n in network_names]
        self.environment.create_interfaces_from_networks(networks=networks,
                                                         node=self)

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

        for diskname, capacity in disknames_capacity.items():
            self.attach_disk(name=diskname,
                             capacity=capacity,
                             force_define=force_define)

    def attach_disk(self, name, capacity, format='qcow2',
                    device='disk', bus='virtio', force_define=False):
        """Attach disk to node


        param: disknames_capacity: Dict
        param: format: String
        param: device: String
        param: bus: String
        param: force_define: Bool
            :rtype : Volume
        """
        vol_name = "%s-%s" % (self.name, name)
        new_vol = self.environment.add_empty_volume(node=self,
                                                    name=vol_name,
                                                    capacity=capacity,
                                                    device=device,
                                                    bus=bus)
        if force_define:
            new_vol.define()
        return new_vol

    @classmethod
    def node_create(cls, name, environment=None, role=None, vcpu=1,
                    memory=1024, has_vnc=True, metadata=None, hypervisor='kvm',
                    os_type='hvm', architecture='x86_64', boot=None):
        """Create node

        :rtype : Node
        """
        if not boot:
            boot = ['network', 'cdrom', 'hd']
        node = cls.objects.create(
            name=name, environment=environment,
            role=role, vcpu=vcpu, memory=memory,
            has_vnc=has_vnc, metadata=metadata, hypervisor=hypervisor,
            os_type=os_type, architecture=architecture, boot=json.dumps(boot)
        )
        return node
