#    Copyright 2013 - 2014 Mirantis, Inc.
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

import ipaddr
import datetime
from time import sleep
import libvirt
import uuid
import xml.etree.ElementTree as ET

from devops.driver.libvirt.libvirt_xml_builder import LibvirtXMLBuilder
from devops.models.base import ParamField
from devops.models.driver import Driver
from devops.models.network import L2NetworkDevice
from devops.models.volume import Volume
from devops.models.node import Node
from devops.helpers.helpers import _get_file_size
from devops.helpers.helpers import _underscored
from devops.helpers.helpers import deepgetattr
from devops.helpers import loader
from devops.helpers.retry import retry
from devops.helpers.lazy import lazy, lazy_property
from devops.helpers import scancodes
from devops import logger


class _LibvirtManagerBase(object):

    def __init__(self):
        libvirt.virInitialize()
        self.connections = {}

    def _create_conn(self, connection_string):
        conn = libvirt.open(connection_string)
        self.connections[connection_string] = conn

    def get_connection(self, connection_string):
        if connection_string not in self.connections:
            conn = libvirt.open(connection_string)
            self.connections[connection_string] = conn
        else:
            conn = self.connections[connection_string]
        return conn


LibvirtManager = _LibvirtManagerBase()


class Snapshot(object):

    def __init__(self, snapshot):
        self._snapshot = snapshot
        self._xml = snapshot.getXMLDesc(0)
        self._repr = ""

    @property
    def created(self):
        xml_tree = ET.fromstring(self._xml)

        timestamp = xml_tree.findall('./creationTime')[0].text
        return datetime.datetime.utcfromtimestamp(float(timestamp))

    @property
    def name(self):
        return self._snapshot.getName()

    def __repr__(self):
        if not self._repr:
            self._repr = "<{0} {1}/{2}>".format(
                self.__class__.__name__, self.name, self.created)
        return self._repr


class LibvirtDriver(Driver):
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
    use_hugepages = ParamField()
    vnc_password = ParamField()

    @lazy_property
    def conn(self):
        """Connection to libvirt api
        """
        return LibvirtManager.get_connection(self.connection_string)

    # DRAFT
    def get_model_class(self, class_name, subtype=None):
        if class_name == 'L2NetworkDevice':
            return LibvirtL2NetworkDevice
        elif class_name == 'Volume':
            return LibvirtVolume
        elif class_name == 'Node':
#            if subtype == 'fuel_master':
#                return loader.load_class('LibvirtAdminNode')
#            elif subtype == 'fuel_slave':
#                return loader.load_class('LibvirtSlaveNode')
#            else:
#                return loader.load_class('LibvirtSlaveNode')
            return LibvirtNode

    @lazy
    @retry()
    def get_capabilities(self):
        """Get host capabilities

        :rtype : ET
        """
        return ET.fromstring(self.conn.getCapabilities())

    @retry()
    def node_list(self):
        # virConnect.listDefinedDomains() only returns stopped domains
        #   https://bugzilla.redhat.com/show_bug.cgi?id=839259
        return [item.name() for item in self.conn.listAllDomains()]

    @lazy
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


class LibvirtL2NetworkDevice(L2NetworkDevice):

    uuid = ParamField()
    forward_mode = ParamField(
        default='nat',
        choices=('nat', 'route', 'bridge', 'private',
                 'vepa', 'passthrough', 'hostdev'))
    has_pxe_server = ParamField(default=False)
    has_dhcp_server = ParamField(default=False)
    tftp_root_dir = ParamField()

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
    def network_active(self):
        """Check if network is active

        :type network: Network
            :rtype : Boolean
        """
        return self.driver.conn.networkLookupByUUIDString(self.uuid).isActive()

    @retry()
    def define(self):
        network_name = _underscored(
            deepgetattr(self, 'group.environment.name'),
            self.name,
        )

        addresses = []
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
            bridge_id=self.id,
            addresses=addresses,
            forward=self.forward_mode,
            ip_network=self.address_pool.ip_network,
            stp=self.driver.stp,
            has_pxe_server=self.has_pxe_server,
            has_dhcp_server=self.has_dhcp_server,
            tftp_root_dir=self.tftp_root_dir,
        )
        ret = self.driver.conn.networkDefineXML(xml)
        ret.setAutostart(True)
        self.uuid = ret.UUIDString()

        self.save()

    def start(self):
        self.create(verbose=False)

    @retry()
    def create(self, verbose=False):
        if verbose or not self.is_active():
            self._libvirt_network.create()

    @retry()
    def destroy(self):
        self._libvirt_network.destroy()

    def erase(self):
        self.remove(verbose=False)

    @retry()
    def remove(self, verbose=False):
        if verbose or self.uuid:
            if verbose or self.exists():
                if self.is_active():
                    self._libvirt_network.destroy()
                self._libvirt_network.undefine()
        self.delete()

    @retry()
    def is_active(self):
        """Check if network is active

        :type network_uuid: str
            :rtype : Boolean
        """
        return self._libvirt_network.isActive()

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


class LibvirtVolume(Volume):

    uuid = ParamField()
    capacity = ParamField(default=None)
    format = ParamField(default='qcow2')
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
            capacity = self.capacity

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
        self.save()

        # Upload predefined image to the volume
        if self.source_image is not None:
            self.upload(self.source_image)

    def erase(self):
        self.remove(verbose=False)

    @retry()
    def remove(self, verbose=False):
        if verbose or self.uuid:
            if verbose or self.exists():
                self._libvirt_volume.delete(0)
        self.delete()

    @retry()
    def get_capacity(self):
        """Get volume capacity
        """
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
        """Check if volume exists
        """
        try:
            self.driver.conn.storageVolLookupByKey(self.uuid)
            return True
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_STORAGE_VOL:
                return False
            else:
                raise


class LibvirtNode(Node):

    uuid = ParamField()
    hypervisor = ParamField(default='kvm', choices=['kvm'])
    os_type = ParamField(default='hvm', choices=['hvm'])
    architecture = ParamField(default='x86_64', choices=['x86_64', 'i686'])
    boot = ParamField(default=['network', 'cdrom', 'hd'])
    metadata = ParamField()
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
            disk_devices=local_disk_devices,
            interfaces=local_interfaces,
        )
        logger.info(node_xml)
        self.uuid = self.driver.conn.defineXML(node_xml).UUIDString()

        self.save()

    def start(self):
        self.create(verbose=False)

    @retry()
    def create(self, verbose=False):
        if verbose or not self.is_active():
            self._libvirt_node.create()

    @retry()
    def destroy(self, verbose=False):
        if verbose or self.is_active():
            self._libvirt_node.destroy()

    def erase(self):
        self.remove(verbose=False)

    @retry()
    def remove(self, verbose=False):
        if verbose or self.uuid:
            if verbose or self.exists():
                self.destroy(verbose=False)
                self._libvirt_node.undefineFlags(
                    libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA)

        self.delete()

    @retry()
    def suspend(self, verbose=False):
        if verbose or self.is_active():
            self._libvirt_node.suspend()

    @retry()
    def resume(self, verbose=False):
        if verbose or self.is_active():
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
    def shutdown(self, node):
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

    @retry()
    def snapshot(self, name=None, force=False, description=None):
        if force and self.has_snapshot(name):
            self.erase_snapshot(name)

        xml = LibvirtXMLBuilder.build_snapshot_xml(name, description)
        logger.info(xml)
        domain = self._libvirt_node
        logger.info(domain.state(0))
        domain.snapshotCreateXML(xml, 0)
        logger.info(domain.state(0))

    @retry()
    def revert(self, name=None, destroy=True):
        if destroy:
            self.destroy(verbose=False)
        if self.has_snapshot(name):

            snapshot = self._get_snapshot(name)
            self._libvirt_node.revertToSnapshot(snapshot, 0)
        else:
            print('Domain snapshot for {0} node not found: no domain '
                  'snapshot with matching'
                  ' name {1}'.format(self.name, name))

    def _get_snapshot(self, name):
        """Get snapshot

        :type name: String
            :rtype : libvirt.virDomainSnapshot
        """
        if name is None:
            return self._libvirt_node.snapshotCurrent(0)
        else:
            return self._libvirt_node.snapshotLookupByName(name, 0)

    @retry()
    def get_snapshots(self):
        """Return full snapshots objects"""
        snapshots = self._libvirt_node.listAllSnapshots(0)
        return [Snapshot(snap) for snap in snapshots]

    @retry()
    def erase_snapshot(self, name):
        snapshot = self._get_snapshot(name)
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

    @retry()
    def delete_all_snapshots(self):
        """Delete all snapshots for node
        """
        domain = self._libvirt_node
        for name in domain.snapshotListNames(
                libvirt.VIR_DOMAIN_SNAPSHOT_LIST_ROOTS):
            snapshot = self._get_snapshot(name)
            snapshot.delete(libvirt.VIR_DOMAIN_SNAPSHOT_DELETE_CHILDREN)
