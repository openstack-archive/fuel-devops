vops/#    Copyright 2013 - 2016 Mirantis, Inc.
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

import datetime
import os
import subprocess
from time import sleep
import uuid
import xml.etree.ElementTree as ET

from django.conf import settings
from django.utils.functional import cached_property
import ipaddr
import libvirt

from devops.driver.libvirt.libvirt_xml_builder import LibvirtXMLBuilder
from devops.error import DevopsError
from devops.helpers.helpers import _get_file_size
from devops.helpers.helpers import _underscored
from devops.helpers.helpers import deepgetattr
from devops.helpers.retry import retry
from devops.helpers import scancodes
from devops import logger
from devops.models.base import ParamField
from devops.models.base import ParamMultiField
from devops.models.driver import Driver as DriverBase
from devops.models.network import L2NetworkDevice as L2NetworkDeviceBase
from devops.models.node import Node as NodeBase
from devops.models.volume import Volume as VolumeBase


class _LibvirtManager(object):

    def __init__(self):
        libvirt.virInitialize()
        self.connections = {}

    def get_connection(self, connection_string):
        if connection_string not in self.connections:
            conn = libvirt.open(connection_string)
            self.connections[connection_string] = conn
        else:
            conn = self.connections[connection_string]
        return conn


LibvirtManager = _LibvirtManager()


class Snapshot(object):

    def __init__(self, snapshot):
        self._snapshot = snapshot

    @property
    def xml(self):
        xml = self._snapshot.getXMLDesc(0)
        snapshot_xmltree = ET.fromstring(xml)

        # Get cpu model from domain definition as it is not available
        # in snapshot XML for host-passthrough cpu mode
        cpu = snapshot_xmltree.findall('./domain/cpu')
        if cpu and 'mode' in cpu[0].attrib:
            cpu_mode = cpu[0].get('mode')
            if cpu_mode == 'host-passthrough':
                domain = self._snapshot.getDomain()
                domain_xml = domain.XMLDesc(
                    libvirt.VIR_DOMAIN_XML_UPDATE_CPU)
                domain_xmltree = ET.fromstring(domain_xml)
                cpu_element = domain_xmltree.find('./cpu')
                domain_element = snapshot_xmltree.findall('./domain')[0]
                domain_element.remove(domain_element.findall('./cpu')[0])
                domain_element.append(cpu_element)

        return ET.tostring(snapshot_xmltree)

    @property
    def _xml_tree(self):
        return ET.fromstring(self.xml)

    @property
    def children_num(self):
        return self._snapshot.numChildren()

    @property
    def created(self):
        timestamp = self._xml_tree.findall('./creationTime')[0].text
        return datetime.datetime.utcfromtimestamp(float(timestamp))

    @property
    def disks(self):
        disks = {}
        xml_snapshot_disks = self._xml_tree.find('./disks')
        for xml_disk in xml_snapshot_disks:
            if xml_disk.get('snapshot') == 'external':
                disks[xml_disk.get('name')] = xml_disk.find(
                    'source').get('file')
        return disks

    @property
    def get_type(self):
        """Return snapshot type"""
        snap_memory = self._xml_tree.findall('./memory')[0]
        if snap_memory.get('snapshot') == 'external':
            return 'external'
        for disk in self._xml_tree.iter('disk'):
            if disk.get('snapshot') == 'external':
                return 'external'
        return 'internal'

    @property
    def memory_file(self):
        return self._xml_tree.findall('./memory')[0].get('file')

    @property
    def name(self):
        return self._snapshot.getName()

    @property
    def parent(self):
        return self._snapshot.getParent()

    @property
    def state(self):
        return self._xml_tree.findall('state')[0].text

    def delete(self, flags):
        return self._snapshot.delete(flags)

    def __repr__(self):
        return "<{0} {1}/{2}>".format(self.__class__.__name__,
                                      self.name, self.created)


class Driver(DriverBase):
    """libvirt driver

    :param use_host_cpu: When creating nodes, should libvirt's
        CPU "host-model" mode be used to set CPU settings. If set to False,
        default mode ("custom") will be used.  (default: True)
    """

    connection_string = ParamField(default="qemu:///system")
    storage_pool_name = ParamField(default="default")
    stp = ParamField(default=True)
    hpet = ParamField(default=True)
    use_host_cpu = ParamField(default=True)
    reboot_timeout = ParamField()
    use_hugepages = ParamField(default=False)
    vnc_password = ParamField()

    @cached_property
    def conn(self):
        """Connection to libvirt api"""
        return LibvirtManager.get_connection(self.connection_string)

    def get_capabilities(self):
        """Get host capabilities

        This method is deprecated. Use `capabilities` property instead.

        :rtype : ET
        """
        return self.capabilities

    @cached_property
    @retry()
    def capabilities(self):
        return ET.fromstring(self.conn.getCapabilities())

    @retry()
    def node_list(self):
        # virConnect.listDefinedDomains() only returns stopped domains
        #   https://bugzilla.redhat.com/show_bug.cgi?id=839259
        return [item.name() for item in self.conn.listAllDomains()]

    @retry()
    def get_allocated_networks(self):
        """Get list of allocated networks

            :rtype : List
        """
        allocated_networks = []
        for network_name in self.conn.listDefinedNetworks():
            et = ET.fromstring(
                self.conn.networkLookupByName(network_name).XMLDesc(0))
            ip = et.find('ip[@address]')
            if ip is not None:
                address = ip.get('address')
                prefix_or_netmask = ip.get('prefix') or ip.get('netmask')
                allocated_networks.append(ipaddr.IPNetwork(
                    "{0:>s}/{1:>s}".format(address, prefix_or_netmask)))
        return allocated_networks

    def get_libvirt_version(self):
        return self.conn.getLibVersion()


class L2NetworkDevice(L2NetworkDeviceBase):
    """L2 network device based on libvirt Network

       Template example
       ----------------
       # Nodes should have at least two interfaces connected to the following
       # L2 networks:
       # admin: for admin/PXE network
       # openstack_br: for all other tagged networks.

       l2_network_devices:  # Libvirt bridges. It is *NOT* Nailgun networks

         # Admin/PXE network
         # Virtual nodes can be connected here (Fuel master, OpenStack nodes).
         # A physical interface ${BAREMETAL_ADMIN_IFACE} will be added
         # to the libvirt network with name 'admin' to allow connectivity
         # between VMs, baremetal servers and system tests on this server.
         admin:
           address_pool: fuelweb_admin-pool01
           dhcp: false
           forward:
             mode: nat
           parent_iface:
             phys_dev: !os_env BAREMETAL_ADMIN_IFACE

         # Libvirt bridge dedicated for access to a baremetal network
         # ${BAREMETAL_OS_NETS_IFACE} with tagged OpenStack networks.
         # This is intermediate bridge, where tagged interfaces with tags
         # 100, 101 and 102 will be created, to get untagged access
         # to the tagged networks.
         # IT IS *NOT* FOR ADDING ADDRESS POOLS!
         # ONLY FOR CONNECTING VM's INTERFACES!
         openstack_br:
           vlan_ifaces:
            - 100
            - 101
            - 102
            - 103
           parent_iface:
             phys_dev: !os_env BAREMETAL_OS_NETS_IFACE

         # Public libvirt bridge, only for keeping IP address.
         # 'nat' forward can be ommited if the baremetal network has
         # it's own gateway.
         # This l2 libvirt network can be ommited if no access required
         # from system tests to the nodes via public addresses.
         # IT IS *NOT* FOR CONNECTING VM's INTERFACES!
         # ONLY FOR ACCESS TO THE PUBLIC NETWORK ADDRESSES
         # AND 'NAT' FROM PUBLIC TO WAN.
         public:
           address_pool: public-pool01
           dhcp: false
           forward:
             mode: nat
           parent_iface:
             l2_net_dev: openstack_br
             tag: 100

         # Storage libvirt bridge, only for keeping IP address.
         # This l2 libvirt network can be ommited if no access required
         # from system tests to the nodes via storage addresses.
         # IT IS *NOT* FOR CONNECTING VM's INTERFACES!
         # ONLY FOR ACCESS TO THE STORAGE NETWORK ADDRESSES
         storage:
           address_pool: storage-pool01
           dhcp: false
           parent_iface:
             l2_net_dev: openstack_br
             tag: 101

         # Management libvirt bridge, only for keeping IP address.
         # This l2 libvirt network can be ommited if no access required
         # from system tests to the nodes via management addresses.
         # IT IS *NOT* FOR CONNECTING VM's INTERFACES!
         # ONLY FOR ACCESS TO THE MANAGEMENT NETWORK ADDRESSES
         management:
           address_pool: management-pool01
           dhcp: false
           parent_iface:
             l2_net_dev: openstack_br
             tag: 102

         # Private libvirt bridge, only for keeping IP address.
         # This l2 libvirt network can be ommited if no access required
         # from system tests to the nodes via private addresses.
         # IT IS *NOT* FOR CONNECTING VM's INTERFACES!
         # ONLY FOR ACCESS TO THE PRIVATE NETWORK ADDRESSES
         private:
           address_pool: private-pool01
           dhcp: false
           parent_iface:
             l2_net_dev: openstack_br
             tag: 103

    """
    uuid = ParamField()

    forward = ParamMultiField(
        mode=ParamField(
            choices=(None, 'nat', 'route', 'bridge', 'private',
                     'vepa', 'passthrough', 'hostdev'),
        )
    )
    #  TODO(ddmitriev): use 'dhcp atttibute' instead of has_dhcp_server
    dhcp = ParamField(default=False)

    has_pxe_server = ParamField(default=False)
    has_dhcp_server = ParamField(default=False)
    tftp_root_dir = ParamField()

    vlan_ifaces = ParamField(default=[])
    parent_iface = ParamMultiField(
        phys_dev=ParamField(default=None),
        l2_net_dev=ParamField(default=None),
        tag=ParamField(default=None),
    )

    @property
    def _libvirt_network(self):
        return self.driver.conn.networkLookupByUUIDString(self.uuid)

    @retry()
    def bridge_name(self):
        return self._libvirt_network.bridgeName()

    @retry()
    def network_name(self):
        """Get network name

            :rtype : String
        """
        return self._libvirt_network.name()

    @retry()
    def is_active(self):
        """Check if network is active

        :type network_uuid: str
            :rtype : Boolean
        """
        return self._libvirt_network.isActive()

    @retry()
    def define(self):
        network_name = _underscored(
            deepgetattr(self, 'group.environment.name'),
            self.name,
        )

        bridge_name = 'virbr{0}'.format(self.id)

        # TODO(ddmitriev): check if 'vlan' package installed
        # Define tagged interfaces on the bridge
        for vlanid in self.vlan_ifaces:
            self.iface_define(name=bridge_name, vlanid=vlanid)

        # Define libvirt network
        ip_network_address = None
        ip_network_prefixlen = None
        dhcp_range_start = None
        dhcp_range_end = None
        addresses = []
        if self.address_pool is not None:
            # Reserved names 'l2_network_device' and 'dhcp'
            ip_network_address = self.address_pool.get_ip('l2_network_device')
            ip_network_prefixlen = str(self.address_pool.ip_network.prefixlen)
            dhcp_range_start = self.address_pool.ip_range_start('dhcp')
            dhcp_range_end = self.address_pool.ip_range_end('dhcp')

            for interface in self.interfaces:
                for address in interface.addresses:
                    ip_addr = ipaddr.IPAddress(address.ip_address)
                    if ip_addr in self.address_pool.ip_network:
                        addresses.append(dict(
                            mac=str(interface.mac_address),
                            ip=str(address.ip_address),
                            name=interface.node.name
                        ))

        xml = LibvirtXMLBuilder.build_network_xml(
            network_name=network_name,
            bridge_name=bridge_name,
            addresses=addresses,
            forward=self.forward.mode,
            ip_network_address=ip_network_address,
            ip_network_prefixlen=ip_network_prefixlen,
            dhcp_range_start=dhcp_range_start,
            dhcp_range_end=dhcp_range_end,
            stp=self.driver.stp,
            has_pxe_server=self.has_pxe_server,
            has_dhcp_server=self.has_dhcp_server,
            tftp_root_dir=self.tftp_root_dir,
        )
        ret = self.driver.conn.networkDefineXML(xml)
        ret.setAutostart(True)
        self.uuid = ret.UUIDString()

        super(L2NetworkDevice, self).define()

    def start(self):
        self.create()

    @retry()
    def create(self, **kwargs):
        if not self.is_active():
            self._libvirt_network.create()

        # Insert a specified interface into the network's bridge
        parent_name = ''
        if self.parent_iface.phys_dev is not None:
            # TODO(ddmitriev): check that phys_dev is not the device
            # that is used for default route
            parent_name = self.parent_iface.phys_dev

        elif self.parent_iface.l2_net_dev is not None:
            l2_net_dev = self.group.get_l2_network_device(
                name=self.parent_iface.l2_net_dev)
            parent_name = l2_net_dev.bridge_name()

        # Add specified interface to the current bridge
        if parent_name is not '':
            if self.parent_iface.tag:
                parent_iface_name = "{0}.{1}".format(
                    parent_name, str(self.parent_iface.tag))
            else:
                parent_iface_name = parent_name
            # TODO(ddmitriev): check that the parent_name is not included
            # to any bridge before adding it to the current bridge
            # TODO(ddmitriev): check if the parent_name is UP
            # before adding it to the bridge
            cmd = 'sudo brctl addif {br} {iface}'.format(
                br=self.bridge_name(), iface=parent_iface_name)
            subprocess.check_output(cmd.split())

    @retry()
    def destroy(self):
        self._libvirt_network.destroy()

    @retry()
    def remove(self, **kwargs):
        if self.uuid:
            if self.exists():
                # Stop network
                if self.is_active():
                    self._libvirt_network.destroy()
                # Remove tagged interfaces
                for vlanid in self.vlan_ifaces:
                    iface_name = "{}.{}".format(self.bridge_name(),
                                                str(vlanid))
                    self.iface_undefine(iface_name=iface_name)
                # Remove network
                self._libvirt_network.undefine()
        super(L2NetworkDevice, self).remove()

    @retry()
    def exists(self):
        """Check if network exists

        :type network_uuid: str
            :rtype : Boolean
        """
        try:
            self.driver.conn.networkLookupByUUIDString(self.uuid)
            return True
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_NETWORK:
                return False
            else:
                raise

    @retry()
    def iface_define(self, name, ip=None, prefix=None, vlanid=None):
        """Define bridge interface

        :type name: String
        :type ip: IPAddress
        :type prefix: Integer
        :type vlanid: Integer
            :rtype : None
        """
        self.driver.conn.interfaceDefineXML(
            LibvirtXMLBuilder.build_iface_xml(name, ip, prefix, vlanid))

    @retry()
    def iface_undefine(self, iface_name):
        """Start interface

        :type iface_name: String
            :rtype : None
        """
        try:
            iface = self.driver.conn.interfaceLookupByName(iface_name)
        except libvirt.libvirtError:
            return None
        iface.undefine()


class Volume(VolumeBase):

    uuid = ParamField()
    capacity = ParamField(default=None)
    format = ParamField(default='qcow2', choices=('qcow2', 'raw'))
    source_image = ParamField(default=None)

    @property
    def _libvirt_volume(self):
        return self.driver.conn.storageVolLookupByKey(self.uuid)

    @retry()
    def define(self):
        name = _underscored(
            deepgetattr(self, 'node.group.environment.name'),
            deepgetattr(self, 'node.name'),
            self.name,
        )

        backing_store_path = None
        backing_store_format = None
        if self.backing_store is not None:
            backing_store_path = self.backing_store.get_path()
            backing_store_format = self.backing_store.format

        if self.source_image is not None:
            capacity = _get_file_size(self.source_image)
        else:
            capacity = int(self.capacity * 1024 ** 3)

        pool_name = self.driver.storage_pool_name
        pool = self.driver.conn.storagePoolLookupByName(pool_name)
        xml = LibvirtXMLBuilder.build_volume_xml(
            name=name,
            capacity=capacity,
            format=self.format,
            backing_store_path=backing_store_path,
            backing_store_format=backing_store_format,
        )
        libvirt_volume = pool.createXML(xml, 0)
        self.uuid = libvirt_volume.key()
        super(Volume, self).define()

        # Upload predefined image to the volume
        if self.source_image is not None:
            self.upload(self.source_image)

    @retry()
    def remove(self, **kwargs):
        if self.uuid:
            if self.exists():
                self._libvirt_volume.delete(0)
        super(Volume, self).remove()

    @retry()
    def get_capacity(self):
        """Get volume capacity"""
        return self._libvirt_volume.info()[1]

    @retry()
    def get_format(self):
        xml_desc = ET.fromstring(self._libvirt_volume.XMLDesc(0))
        return xml_desc.find('target/format[@type]').get('type')

    @retry()
    def get_path(self):
        return self._libvirt_volume.path()

    def fill_from_exist(self):
        self.capacity = self.get_capacity()
        self.format = self.get_format()

    @retry(count=2)
    def upload(self, path):
        size = _get_file_size(path)
        with open(path, 'rb') as fd:
            stream = self.driver.conn.newStream(0)
            self._libvirt_volume.upload(
                stream=stream, offset=0,
                length=size, flags=0)
            stream.sendAll(self.chunk_render, fd)
            stream.finish()

    def chunk_render(self, stream, size, fd):
        return fd.read(size)

    @retry()
    def get_allocation(self):
        """Get allocated volume size

        :rtype : int
        """
        return self._libvirt_volume.info()[2]

    @retry()
    def exists(self):
        """Check if volume exists"""
        try:
            self.driver.conn.storageVolLookupByKey(self.uuid)
            return True
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_STORAGE_VOL:
                return False
            else:
                raise

    # Changed behaviour. It is not a @classmethod anymore; thus
    # 'backing_store' variable deprecated, child of the current snapshot
    # will be created.
    def create_child(self, name):
        """Create new volume based on current volume

        :rtype : Volume
        """
        cls = self.driver.get_model_class('Volume')
        return cls.objects.create(
            name=name,
            capacity=self.capacity,
            node=self.node,
            format=self.format,
            backing_store=self,
        )

    # TO REWRITE, LEGACY, for fuel-qa compatibility
    # Used for EXTERNAL SNAPSHOTS
    @classmethod
    def volume_get_predefined(cls, uuid):
        """Get predefined volume

        :rtype : Volume
        """
        try:
            volume = cls.objects.get(uuid=uuid)
        except cls.DoesNotExist:
            volume = cls(uuid=uuid)
        volume.fill_from_exist()
        volume.save()
        return volume


class Node(NodeBase):

    uuid = ParamField()
    hypervisor = ParamField(default='kvm', choices=('kvm', 'test'))
    os_type = ParamField(default='hvm', choices=['hvm'])
    architecture = ParamField(default='x86_64', choices=['x86_64', 'i686'])
    boot = ParamField(default=['network', 'cdrom', 'hd'])
    vcpu = ParamField(default=1)
    memory = ParamField(default=1024)
    has_vnc = ParamField(default=True)

    @property
    def _libvirt_node(self):
        return self.driver.conn.lookupByUUIDString(self.uuid)

    @retry()
    def get_vnc_port(self):
        """Get VNC port

            :rtype : String
        """
        xml_desc = ET.fromstring(
            self._libvirt_node.XMLDesc(0))
        vnc_element = xml_desc.find('devices/graphics[@type="vnc"][@port]')
        if vnc_element is not None:
            return vnc_element.get('port')

    @property
    def vnc_password(self):
        return self.driver.vnc_password

    @retry()
    def exists(self):
        """Check if node exists

            :rtype : Boolean
        """
        try:
            self.driver.conn.lookupByUUIDString(self.uuid)
            return True
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_DOMAIN:
                return False
            else:
                raise

    @retry()
    def is_active(self):
        """Check if node is active

            :rtype : Boolean
        """
        return self._libvirt_node.isActive()

    @retry()
    def send_keys(self, keys):
        """Send keys to node

        :type keys: String
            :rtype : None
        """
        key_codes = scancodes.from_string(str(keys))
        for key_code in key_codes:
            if isinstance(key_code[0], str):
                if key_code[0] == 'wait':
                    sleep(1)
                continue
            self._libvirt_node.sendKey(0, 0, list(key_code), len(key_code), 0)

    @retry()
    def define(self):
        """Define node

            :rtype : None
        """
        name = _underscored(
            deepgetattr(self, 'group.environment.name'),
            self.name,
        )

        local_disk_devices = []
        for disk in self.disk_devices:
            local_disk_devices.append(dict(
                disk_type=disk.type,
                disk_device=disk.device,
                disk_volume_format=disk.volume.format,
                disk_volume_path=disk.volume.get_path(),
                disk_bus=disk.bus,
                disk_target_dev=disk.target_dev,
                disk_serial=uuid.uuid4().hex,
            ))

        local_interfaces = []
        for interface in self.interfaces:
            if interface.type != 'network':
                raise NotImplementedError(
                    message='Interface types different from network are not '
                            'implemented yet')

            l2_dev = interface.l2_network_device
            local_interfaces.append(dict(
                interface_type=interface.type,
                interface_mac_address=interface.mac_address,
                interface_network_name=l2_dev.network_name(),
                interface_id=interface.id,
                interface_model=interface.model,
            ))

        emulator = self.driver.get_capabilities().find(
            'guest/arch[@name="{0:>s}"]/'
            'domain[@type="{1:>s}"]/emulator'.format(
                self.architecture, self.hypervisor)).text
        node_xml = LibvirtXMLBuilder.build_node_xml(
            name=name,
            hypervisor=self.hypervisor,
            use_host_cpu=self.driver.use_host_cpu,
            vcpu=self.vcpu,
            memory=self.memory,
            use_hugepages=self.driver.use_hugepages,
            hpet=self.driver.hpet,
            os_type=self.os_type,
            architecture=self.architecture,
            boot=self.boot,
            reboot_timeout=self.driver.reboot_timeout,
            should_enable_boot_menu=self.should_enable_boot_menu,
            emulator=emulator,
            has_vnc=self.has_vnc,
            vnc_password=self.driver.vnc_password,
            local_disk_devices=local_disk_devices,
            interfaces=local_interfaces,
        )
        logger.info(node_xml)
        self.uuid = self.driver.conn.defineXML(node_xml).UUIDString()

        super(Node, self).define()

    def start(self):
        self.create()

    @retry()
    def create(self, **kwargs):
        if not self.is_active():
            self._libvirt_node.create()

    @retry()
    def destroy(self, **kwargs):
        if self.is_active():
            self._libvirt_node.destroy()

    @retry()
    def remove(self, **kwargs):
        if self.uuid:
            if self.exists():
                self.destroy()

                # EXTERNAL SNAPSHOTS
                for snapshot in self.get_snapshots():
                    self._delete_snapshot_files(snapshot)

                # ORIGINAL SNAPSHOTS
                self._libvirt_node.undefineFlags(
                    libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA)
        super(Node, self).remove()

    @retry()
    def suspend(self, **kwargs):
        if self.is_active():
            self._libvirt_node.suspend()

    @retry()
    def resume(self, **kwargs):
        if self.is_active():
            domain = self._libvirt_node
            if domain.info()[0] == libvirt.VIR_DOMAIN_PAUSED:
                domain.resume()

    @retry()
    def reboot(self):
        """Reboot node

            :rtype : None
        """
        self._libvirt_node.reboot()

    @retry()
    def shutdown(self):
        """Shutdown node

            :rtype : None
        """
        self._libvirt_node.shutdown()

    @retry()
    def reset(self):
        self._libvirt_node.reset()

    @retry()
    def has_snapshot(self, name):
        return name in self._libvirt_node.snapshotListNames()

    # EXTERNAL SNAPSHOT
    def snapshot_create_child_volumes(self, name):
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
                vol_child = disk.volume.create_child(
                    name='{0}.{1}'.format(back_vol_name, name),
                )
                vol_child.define()

                # update disk node to new snapshot
                disk.volume = vol_child
                disk.save()

    # EXTERNAL SNAPSHOT
    def _assert_snapshot_type(self, external=False):
        # If domain has snapshots we must check their type

        # TODO(ddmitriev)
        snap_list = self.get_snapshots()

        if len(snap_list) > 0:
            snap_type = snap_list[0].get_type
            if external and snap_type == 'internal':
                raise DevopsError(
                    "Cannot create external snapshot when internal exists")
            if not external and snap_type == 'external':
                raise DevopsError(
                    "Cannot create internal snapshot when external exists")

    # EXTERNAL SNAPSHOT
    def set_snapshot_current(self, name):
        snapshot = self._get_snapshot(name)

        # DOESN'T WORK if DRIVER_USE_HOST_CPU=True
        # In snapshot.xml is not appeared cpu tag <model>
        # from the snapshot XML file,
        # causing the following error:
        #   libvirtError: unsupported configuration: \
        #   Target CPU model <null> does not match source SandyBridge
        self._libvirt_node.snapshotCreateXML(
            snapshot.xml,
            libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE |
            libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT)

    @retry()
    def snapshot(self, name=None, force=False, description=None,
                 disk_only=False, external=False):

        # Erase existing snapshot or raise an error if already exists
        if self.has_snapshot(name):
            if force:
                self.erase_snapshot(name)
            else:
                raise DevopsError("Snapshot with name {0} already exists"
                                  .format(name))

        # Check that existing snapshot has the same type
        self._assert_snapshot_type(external=external)

        local_disk_devices = []
        if external:
            # EXTERNAL SNAPSHOTS
            if self.driver.get_libvirt_version() < 1002012:
                raise DevopsError(
                    "For external snapshots we need libvirtd >= 1.2.12")

            # Check whether we have directory for snapshots, if not
            # create it
            if not os.path.exists(settings.SNAPSHOTS_EXTERNAL_DIR):
                os.makedirs(settings.SNAPSHOTS_EXTERNAL_DIR)

            # create new volume which will be used as
            # disk for snapshot changes
            self.snapshot_create_child_volumes(name)

            base_memory_file = '{0}/snapshot-memory-{1}_{2}.{3}'.format(
                settings.SNAPSHOTS_EXTERNAL_DIR,
                deepgetattr(self, 'group.environment.name'),
                self.name,
                name)
            file_count = 0
            memory_file = base_memory_file
            while os.path.exists(memory_file):
                memory_file = base_memory_file + '-' + str(file_count)
                file_count += 1

            for disk in self.disk_devices:
                if disk.device == 'disk':
                    local_disk_devices.append(dict(
                        disk_volume_path=disk.volume.get_path(),
                        disk_target_dev=disk.target_dev,
                    ))

            if self.is_active() and not disk_only:
                create_xml_flag = libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REUSE_EXT
            else:
                create_xml_flag = (
                    libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_DISK_ONLY |
                    libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REUSE_EXT
                )

        else:
            # ORIGINAL SNAPSHOTS
            memory_file = ''
            create_xml_flag = 0

        xml = LibvirtXMLBuilder.build_snapshot_xml(
            name=name,
            description=description,
            external=external,
            disk_only=disk_only,
            memory_file=memory_file,
            domain_isactive=self.is_active(),
            local_disk_devices=local_disk_devices
        )

        domain = self._libvirt_node
        logger.info(xml)
        logger.info(domain.state(0))

        domain.snapshotCreateXML(xml, create_xml_flag)

        if external:
            self.set_snapshot_current(name)

        logger.info(domain.state(0))

    # EXTERNAL SNAPSHOT
    def _delete_snapshot_files(self, snapshot):
        """Delete snapshot external files"""
        snap_type = snapshot.get_type
        if snap_type == 'external':
            for snap_file in self._get_snapshot_files(snapshot):
                if os.path.isfile(snap_file):
                    try:
                        os.remove(snap_file)
                        logger.info(
                            "Delete external snapshot file {0}".format(
                                snap_file))
                    except Exception:
                        logger.info(
                            "Cannot delete external snapshot file {0}"
                            " must be deleted from cron script".format(
                                snap_file))

    # EXTERNAL SNAPSHOT
    def _get_snapshot_files(self, snapshot):
        """Return snapshot files"""
        snap_files = []
        snap_memory = snapshot._xml_tree.findall('./memory')[0]
        if snap_memory.get('file') is not None:
            snap_files.append(snap_memory.get('file'))
        return snap_files

    # EXTERNAL SNAPSHOT
    def _redefine_external_snapshot(self, name=None):
        snapshot = self._get_snapshot(name)

        logger.info("Revert {0} ({1}) from external snapshot {2}".format(
            self.name, snapshot.state, name))

        self.destroy()

        # When snapshot dont have children we need to update disks in XML
        # used for reverting, standard revert function will restore links
        # to original disks, but we need to use disks with snapshot point,
        # we dont want to change original data
        #
        # For snapshot with children we need to create new snapshot chain
        # and we need to start from original disks, this disks will get new
        # snapshot point in node class
        xml_domain = snapshot._xml_tree.find('domain')
        if snapshot.children_num == 0:
            domain_disks = xml_domain.findall('./devices/disk')
            for s_disk, s_disk_data in snapshot.disks.items():
                for d_disk in domain_disks:
                    d_disk_dev = d_disk.find('target').get('dev')
                    d_disk_device = d_disk.get('device')
                    if d_disk_dev == s_disk and d_disk_device == 'disk':
                        d_disk.find('source').set('file', s_disk_data)

        if snapshot.state == 'shutoff':
            # Redefine domain for snapshot without memory save
            self.driver.conn.defineXML(ET.tostring(xml_domain))
        else:
            self.driver.conn.restoreFlags(
                snapshot.memory_file,
                dxml=ET.tostring(xml_domain),
                flags=libvirt.VIR_DOMAIN_SAVE_PAUSED)

        # set snapshot as current
        self.set_snapshot_current(name)

    def _update_disks_from_snapshot(self, name):
        """Update actual node disks volumes to disks from snapshot

           This method change disks attached to actual node to
           disks used in snapshot. This is required to save correct
           state of node disks. We use node disks as a backend when
           new snapshots are created.
        """
        snapshot = self._get_snapshot(name)

        for snap_disk, snap_disk_file in snapshot.disks.items():
            for disk in self.disk_devices:
                if snap_disk == disk.target_dev:
                    if snapshot.children_num == 0:
                        disk.volume = self.get_volume(uuid=snap_disk_file)
                    else:
                        disk.volume = self.get_volume(
                            uuid=snap_disk_file).backing_store
                    disk.save()

    @retry()
    def _node_revert_snapshot_recreate_disks(self, name):
        """Recreate snapshot disks."""
        snapshot = self._get_snapshot(name)

        if snapshot.children_num == 0:
            for s_disk, s_disk_data in snapshot.disks.items():
                logger.info("Recreate {0}".format(s_disk_data))

                # Save actual volume XML, delete volume and create
                # new from saved XML
                volume = self.driver.conn.storageVolLookupByKey(s_disk_data)
                volume_xml = volume.XMLDesc()
                volume_pool = volume.storagePoolLookupByVolume()
                volume.delete()
                volume_pool.createXML(volume_xml)

    def _revert_external_snapshot(self, name=None):
        snapshot = self._get_snapshot(name)
        self.destroy()
        if snapshot.children_num == 0:
            logger.info("Reuse last snapshot")

            # Update current node disks
            self._update_disks_from_snapshot(name)

            # Recreate volumes for snapshot and reuse it.
            self._node_revert_snapshot_recreate_disks(name)

            # Revert snapshot
            # self.driver.node_revert_snapshot(node=self, name=name)
            self._redefine_external_snapshot(name=name)
        else:
            # Looking for last reverted snapshot without children
            # or create new and start next snapshot chain
            revert_name = name + '-revert'
            revert_count = 0
            create_new = True

            while self.has_snapshot(revert_name):
                # Check wheter revert snapshot has children
                snapshot_revert = self._get_snapshot(revert_name)
                if snapshot_revert.children_num == 0:
                    logger.info(
                        "Revert snapshot exists, clean and reuse it")

                    # Update current node disks
                    self._update_disks_from_snapshot(revert_name)

                    # Recreate volumes
                    self._node_revert_snapshot_recreate_disks(revert_name)

                    # Revert snapshot
                    # self.driver.node_revert_snapshot(
                    #    node=self, name=revert_name)
                    self._redefine_external_snapshot(name=revert_name)
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
                # self.driver.node_revert_snapshot(node=self, name=name)
                self._redefine_external_snapshot(name=name)

                # Create new snapshot
                self.snapshot(name=revert_name, external=True)

    @retry()
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
        if destroy:
            self.destroy()
        if self.has_snapshot(name):
            snapshot = self._get_snapshot(name)

            if snapshot.get_type == 'external':
                # EXTERNAL SNAPSHOT
                self._revert_external_snapshot(name)
            else:
                # ORIGINAL SNAPSHOT
                logger.info("Revert {0} ({1}) to internal snapshot {2}".format(
                    self.name, snapshot.state, name))
                self._libvirt_node.revertToSnapshot(snapshot._snapshot, 0)

        else:
            raise DevopsError(
                'Domain snapshot for {0} node not found: no domain '
                'snapshot with matching'
                ' name {1}'.format(self.name, name))

    def _get_snapshot(self, name):
        """Get snapshot

        :type name: String
            :rtype : Snapshot(libvirt.virDomainSnapshot)
        """
        if name is None:
            return Snapshot(self._libvirt_node.snapshotCurrent(0))
        else:
            return Snapshot(self._libvirt_node.snapshotLookupByName(name, 0))

    @retry()
    def get_snapshots(self):
        """Return full snapshots objects"""
        snapshots = self._libvirt_node.listAllSnapshots(0)
        return [Snapshot(snap) for snap in snapshots]

    @retry()
    def erase_snapshot(self, name):
        if self.has_snapshot(name):

            snapshot = self._get_snapshot(name)
            snap_type = snapshot.get_type
            if snap_type == 'external':
                # EXTERNAL SNAPSHOT DELETE
                if snapshot.children_num > 0:
                    logger.error("Cannot delete external snapshots "
                                 "with children")
                    return

                self.destroy()

                # Update domain to snapshot state
                xml_domain = snapshot._xml_tree.find('domain')
                self.driver.conn.defineXML(ET.tostring(xml_domain))
                self._delete_snapshot_files(snapshot)
                snapshot.delete(2)

                for disk in self.disk_devices:
                    if disk.device == 'disk':
                        snap_disk = disk.volume
                        # update disk on node
                        disk.volume = disk.volume.backing_store
                        disk.save()
                        snap_disk.remove()

            else:
                # ORIGINAL DELETE
                snapshot.delete(0)

    @retry()
    def set_vcpu(self, vcpu):
        """Set vcpu count on node

        param: vcpu: Integer
            :rtype : None
        """
        if vcpu is not None and vcpu != self.vcpu:
            self.vcpu = vcpu
            domain = self._libvirt_node
            domain.setVcpusFlags(vcpu, 4)
            domain.setVcpusFlags(vcpu, 2)
            self.save()

    @retry()
    def set_memory(self, memory):
        """Set memory size on node

        param: memory: Integer
            :rtype : None
        """
        if memory is not None and memory != self.memory:
            self.memory = memory
            domain = self._libvirt_node
            domain.setMaxMemory(memory * 1024)
            domain.setMemoryFlags(memory * 1024, 2)
            self.save()

    @retry()
    def get_interface_target_dev(self, mac):
        """Get target device

        :type mac: String
            :rtype : String
        """
        xml_desc = ET.fromstring(self._libvirt_node.XMLDesc(0))
        target = xml_desc.find('.//mac[@address="%s"]/../target' % mac)
        if target is not None:
            return target.get('dev')


#    #LEGACY, TO REMOVE, NOT USED ANYWHERE
#    @retry()
#    def delete_all_snapshots(self):
#        """Delete all snapshots for node
#        """
#        domain = self._libvirt_node
#        for name in domain.snapshotListNames(
#                libvirt.VIR_DOMAIN_SNAPSHOT_LIST_ROOTS):
#            snapshot = self._get_snapshot(name)
#            snapshot.delete(libvirt.VIR_DOMAIN_SNAPSHOT_DELETE_CHILDREN)
