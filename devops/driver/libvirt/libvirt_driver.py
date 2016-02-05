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

import datetime
import os
from time import sleep
import xml.etree.ElementTree as ET

from django.conf import settings
from django.utils.functional import cached_property
import ipaddr
import libvirt

from devops.driver.libvirt.libvirt_xml_builder import LibvirtXMLBuilder
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
        self._domain = snapshot.getDomain()
        self._xml_content = ''
        self._xml = snapshot.getXMLDesc(0)
        self._repr = ""

    @property
    def _xml(self):
        return self._xml_content

    @_xml.setter
    def _xml(self, xml_content):
        snapshot_xmltree = ET.fromstring(xml_content)
        cpu_mode = snapshot_xmltree.findall('./domain/cpu')[0].get('mode')
        # Get cpu model from domain definition as it is not available
        # in snapshot XML for host-passthrough cpu mode
        if cpu_mode == 'host-passthrough':
            domain_xml = self._domain.XMLDesc(
                libvirt.VIR_DOMAIN_XML_UPDATE_CPU)
            domain_xmltree = ET.fromstring(domain_xml)
            cpu_element = domain_xmltree.find('./cpu')
            domain_element = snapshot_xmltree.findall('./domain')[0]
            domain_element.remove(domain_element.findall('./cpu')[0])
            domain_element.append(cpu_element)
        self._xml_content = ET.tostring(snapshot_xmltree)

    @property
    def _xml_tree(self):
        return ET.fromstring(self._xml)

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

    def __repr__(self):
        if not self._repr:
            self._repr = "<{0} {1}/{2}>".format(
                self.__class__.__name__, self.name, self.created)
        return self._repr


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

    uuid = ParamField()

    forward = ParamMultiField(
        mode=ParamField(
            choices=(None, 'nat', 'route', 'bridge', 'private',
                     'vepa', 'passthrough', 'hostdev'),
        )
    )
    dhcp = ParamField(default=False)

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
            forward=self.forward.mode,
            ip_network=self.address_pool.ip_network,
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
        self.create(verbose=False)

    @retry()
    def create(self, verbose=False):
        if verbose or not self.is_active():
            self._libvirt_network.create()

    @retry()
    def destroy(self):
        self._libvirt_network.destroy()

    @retry()
    def remove(self, verbose=False):
        if verbose or self.uuid:
            if verbose or self.exists():
                if self.is_active():
                    self._libvirt_network.destroy()
                self._libvirt_network.undefine()
        super(L2NetworkDevice, self).remove(verbose)

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


class DevopsDriver(object):
    def __init__(self,
                 connection_string="qemu:///system",
                 storage_pool_name="default",
                 stp=True, hpet=True, use_host_cpu=True):
        """libvirt driver

        :param use_host_cpu: When creating nodes, should libvirt's
            CPU "host-model" mode be used to set CPU settings. If set to False,
            default mode ("custom") will be used.  (default: True)
        """
        libvirt.virInitialize()
        self.conn = libvirt.open(connection_string)
        self.xml_builder = LibvirtXMLBuilder(self)
        self.stp = stp
        self.hpet = hpet
        self.capabilities = None
        self.allocated_networks = None
        self.storage_pool_name = storage_pool_name
        self.reboot_timeout = None
        self.use_host_cpu = use_host_cpu
        self.use_hugepages = settings.USE_HUGEPAGES

        if settings.VNC_PASSWORD:
            self.vnc_password = settings.VNC_PASSWORD

        if settings.REBOOT_TIMEOUT:
            self.reboot_timeout = settings.REBOOT_TIMEOUT

    def __del__(self):
        self.conn.close()

    def _get_name(self, *kwargs):
        return self.xml_builder._get_name(*kwargs)

    @retry()
    def node_active(self, node):
        """Check if node is active

        :type node: Node
            :rtype : Boolean
        """
        return self.conn.lookupByUUIDString(node.uuid).isActive()

    @retry()
    def node_exists(self, node):
        """Check if node exists

        :type node: Node
            :rtype : Boolean
        """
        try:
            self.conn.lookupByUUIDString(node.uuid)
            return True
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_DOMAIN:
                return False
            else:
                raise

    @retry()
    def node_snapshot_exists(self, node, name):
        """Check if snapshot exists

        :type node: Node
        :type name: String
            :rtype : Boolean
        """
        ret = self.conn.lookupByUUIDString(node.uuid)
        return name in ret.snapshotListNames()

    @retry()
    def volume_exists(self, volume):
        """Check if volume exists

        :type volume: Volume
            :rtype : Boolean
        """
        try:
            self.conn.storageVolLookupByKey(volume.uuid)
            return True
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_STORAGE_VOL:
                return False
            else:
                raise

    @retry()
    def node_define(self, node):
        """Define node

        :type node: Node
            :rtype : None
        """
        emulator = self.get_capabilities(
        ).find(
            'guest/arch[@name="{0:>s}"]/'
            'domain[@type="{1:>s}"]/emulator'.format(
                node.architecture, node.hypervisor)).text
        node_xml = self.xml_builder.build_node_xml(node, emulator)
        logger.info(node_xml)
        node.uuid = self.conn.defineXML(node_xml).UUIDString()

    @retry()
    def node_destroy(self, node):
        """Destroy node

        :type node: Node
            :rtype : None
        """
        self.conn.lookupByUUIDString(node.uuid).destroy()

    @retry()
    def node_undefine(self, node, undefine_snapshots=False):
        """Undefine domain.

        If undefine_snapshot is set, discard all snapshots.

        :type node: Node
        :type undefine_snapshots: Boolean
            :rtype : None

        """
        domain = self.conn.lookupByUUIDString(node.uuid)
        if undefine_snapshots:
            # Delete external snapshots
            snap_list = domain.listAllSnapshots(0)
            for snapshot in snap_list:
                self._delete_snapshot_files(snapshot)
            domain.undefineFlags(
                libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA)
        else:
            domain.undefine()

    @retry()
    def node_undefine_by_name(self, node_name):
        """Undefine domain discarding all snapshots

        :type node_name: String
            :rtype : None
        """
        domain = self.conn.lookupByName(node_name)
        domain.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA)

    @retry()
    def node_get_vnc_port(self, node):
        """Get VNC port

        :type node: Node
            :rtype : String
        """
        xml_desc = ET.fromstring(
            self.conn.lookupByUUIDString(node.uuid).XMLDesc(0))
        vnc_element = xml_desc.find('devices/graphics[@type="vnc"][@port]')
        if vnc_element is not None:
            return vnc_element.get('port')

    @retry()
    def node_get_interface_target_dev(self, node, mac):
        """Get target device

        :type node: Node
        :type mac: String
            :rtype : String
        """
        xml_desc = ET.fromstring(
            self.conn.lookupByUUIDString(node.uuid).XMLDesc(0))
        target = xml_desc.find('.//mac[@address="%s"]/../target' % mac)
        if target is not None:
            return target.get('dev')

    @retry()
    def node_create(self, node):
        """Create node

        :type node: Node
            :rtype : None
        """
        self.conn.lookupByUUIDString(node.uuid).create()

    @retry()
    def node_reset(self, node):
        """Reset node

        :type node: Node
            :rtype : None
        """
        self.conn.lookupByUUIDString(node.uuid).reset()

    @retry()
    def node_reboot(self, node):
        """Reboot node

        :type node: Node
            :rtype : None
        """
        self.conn.lookupByUUIDString(node.uuid).reboot()

    @retry()
    def node_suspend(self, node):
        """Suspend node

        :type node: Node
            :rtype : None
        """
        self.conn.lookupByUUIDString(node.uuid).suspend()

    @retry()
    def node_resume(self, node):
        """Resume node

        :type node: Node
            :rtype : None
        """
        domain = self.conn.lookupByUUIDString(node.uuid)
        if domain.info()[0] == libvirt.VIR_DOMAIN_PAUSED:
            domain.resume()

    @retry()
    def node_shutdown(self, node):
        """Shutdown node

        :type node: Node
            :rtype : None
        """
        self.conn.lookupByUUIDString(node.uuid).shutdown()

    @retry()
    def node_get_snapshots(self, node):
        """Get list of snapshots

        :rtype : List
            :type node: Node
        """

        snapshots = self.conn.lookupByUUIDString(
            node.uuid).listAllSnapshots(0)
        return [Snapshot(snap) for snap in snapshots]

    def node_get_snapshot(self, node, name):
        """Get snapshot with name

        :rtype : Snapshot
            :type node: Node
            :type name: Snapshot name
        """

        snap = self.conn.lookupByUUIDString(
            node.uuid).snapshotLookupByName(name)
        return Snapshot(snap)

    def node_set_snapshot_current(self, node, name):
        domain = self.conn.lookupByUUIDString(node.uuid)
        snapshot = self._get_snapshot(domain, name)
        snapshot_xml = Snapshot(snapshot)._xml
        domain.snapshotCreateXML(
            snapshot_xml,
            libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE |
            libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT)

    @retry()
    def node_create_snapshot(self, node, name=None, description=None,
                             disk_only=False, external=False):
        """Create snapshot

        :type description: String
        :type name: String
        :type node: Node
            :rtype : None
        """
        if self.node_snapshot_exists(node, name):
            logger.error("Snapshot with name {0} already exists".format(name))
            return

        domain = self.conn.lookupByUUIDString(node.uuid)

        # If domain has snapshots we must check their type
        snap_list = self.node_get_snapshots(node)
        if len(snap_list) > 0:
            snap_type = snap_list[0].get_type
            if external and snap_type == 'internal':
                logger.error(
                    "Cannot create external snapshot when internal exists")
                return
            if not external and snap_type == 'external':
                logger.error(
                    "Cannot create internal snapshot when external exists")
                return

        logger.info(domain.state(0))
        xml = self.xml_builder.build_snapshot_xml(
            name, description, node, disk_only, external,
            settings.SNAPSHOTS_EXTERNAL_DIR)
        logger.info(xml)
        if external:
            # Check whether we have directory for snapshots, if not
            # create it
            if not os.path.exists(settings.SNAPSHOTS_EXTERNAL_DIR):
                os.makedirs(settings.SNAPSHOTS_EXTERNAL_DIR)

            if domain.isActive() and not disk_only:
                domain.snapshotCreateXML(
                    xml,
                    libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REUSE_EXT)
            else:
                domain.snapshotCreateXML(
                    xml,
                    libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_DISK_ONLY |
                    libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REUSE_EXT)
            self.node_set_snapshot_current(node, name)
        else:
            domain.snapshotCreateXML(xml)
        logger.info(domain.state(0))

    def _delete_snapshot_files(self, snapshot):
        """Delete snapshot external files"""
        snap_type = Snapshot(snapshot).get_type
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

    def _get_snapshot(self, domain, name):
        """Get snapshot

        :type domain: Node
        :type name: String
            :rtype : libvirt.virDomainSnapshot
        """
        if name is None:
            return domain.snapshotCurrent(0)
        else:
            return domain.snapshotLookupByName(name, 0)

    def _get_snapshot_files(self, snapshot):
        """Return snapshot files"""
        xml_tree = ET.fromstring(snapshot.getXMLDesc())
        snap_files = []
        snap_memory = xml_tree.findall('./memory')[0]
        if snap_memory.get('file') is not None:
            snap_files.append(snap_memory.get('file'))
        return snap_files

    @retry()
    def node_revert_snapshot_recreate_disks(self, node, name):
        """Recreate snapshot disks."""
        domain = self.conn.lookupByUUIDString(node.uuid)
        snapshot = Snapshot(self._get_snapshot(domain, name))

        if snapshot.children_num == 0:
            for s_disk, s_disk_data in snapshot.disks.items():
                logger.info("Recreate {0}".format(s_disk_data))

                # Save actual volume XML, delete volume and create
                # new from saved XML
                volume = self.conn.storageVolLookupByKey(s_disk_data)
                volume_xml = volume.XMLDesc()
                volume_pool = volume.storagePoolLookupByVolume()
                volume.delete()
                volume_pool.createXML(volume_xml)

    @retry()
    def node_revert_snapshot(self, node, name=None):
        """Revert snapshot for node

        :type node: Node
        :type name: String
            :rtype : None
        """
        domain = self.conn.lookupByUUIDString(node.uuid)
        snapshot = Snapshot(self._get_snapshot(domain, name))

        if snapshot.get_type == 'external':
            logger.info("Revert {0} ({1}) from external snapshot {2}".format(
                node.name, snapshot.state, name))

            if self.node_active(node):
                self.node_destroy(node)

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
                self.conn.defineXML(ET.tostring(xml_domain))
            else:
                self.conn.restoreFlags(
                    snapshot.memory_file,
                    dxml=ET.tostring(xml_domain),
                    flags=libvirt.VIR_DOMAIN_SAVE_PAUSED)

            # set snapshot as current
            self.node_set_snapshot_current(node, name)

        else:
            logger.info("Revert {0} ({1}) to internal snapshot {2}".format(
                node.name, snapshot.state, name))
            domain.revertToSnapshot(snapshot._snapshot, 0)

    @retry()
    def node_delete_all_snapshots(self, node):
        """Delete all snapshots for node

        :type node: Node
        """

        domain = self.conn.lookupByUUIDString(node.uuid)

        # Delete all external snapshots end return
        snap_list = domain.listAllSnapshots(0)
        if len(snap_list) > 0:
            snap_type = Snapshot(snap_list[0]).get_type
            if snap_type == 'external':
                for snapshot in snap_list:
                    snapshot.delete(2)
                return

        for name in domain.snapshotListNames(
                libvirt.VIR_DOMAIN_SNAPSHOT_LIST_ROOTS):
            snapshot = self._get_snapshot(domain, name)
            snapshot.delete(libvirt.VIR_DOMAIN_SNAPSHOT_DELETE_CHILDREN)

    @retry()
    def node_delete_snapshot(self, node, name=None):
        """Delete snapshot

        :type node: Node
        :type name: String
        """
        domain = self.conn.lookupByUUIDString(node.uuid)
        snapshot = self._get_snapshot(domain, name)
        snap_type = Snapshot(snapshot).get_type
        if snap_type == 'external':
            if snapshot.numChildren() > 0:
                logger.error("Cannot delete external snapshots with children")
                return

            if domain.isActive():
                domain.destroy()

            # Update domain to snapshot state
            xml_tree = ET.fromstring(snapshot.getXMLDesc())
            xml_domain = xml_tree.find('domain')
            self.conn.defineXML(ET.tostring(xml_domain))
            self._delete_snapshot_files(snapshot)
            snapshot.delete(2)
        else:
            snapshot.delete(0)

    @retry()
    def node_send_keys(self, node, keys):
        """Send keys to node

        :type node: Node
        :type keys: String
            :rtype : None
        """

        key_codes = scancodes.from_string(str(keys))
        for key_code in key_codes:
            if isinstance(key_code[0], str):
                if key_code[0] == 'wait':
                    sleep(1)
                continue
            self.conn.lookupByUUIDString(node.uuid).sendKey(0, 0,
                                                            list(key_code),
                                                            len(key_code), 0)

    @retry()
    def node_set_vcpu(self, node, vcpu):
        """Set VCPU

        :type volume: Volume
            :rtype : None
        """
        domain = self.conn.lookupByUUIDString(node.uuid)
        domain.setVcpusFlags(vcpu, 4)
        domain.setVcpusFlags(vcpu, 2)

    @retry()
    def node_set_memory(self, node, memory):
        """Set VCPU

        :type volume: Volume
            :rtype : None
        """
        domain = self.conn.lookupByUUIDString(node.uuid)
        domain.setMaxMemory(memory)
        domain.setMemoryFlags(memory, 2)

    @retry()
    def volume_define(self, volume, pool=None):
        """Define volume

        :type volume: Volume
        :type pool: String
            :rtype : None
        """
        if pool is None:
            pool = self.storage_pool_name
        libvirt_volume = self.conn.storagePoolLookupByName(pool).createXML(
            self.xml_builder.build_volume_xml(volume), 0)
        volume.uuid = libvirt_volume.key()

    @retry()
    def volume_list(self, pool=None):
        if pool is None:
            pool = self.storage_pool_name
        return self.conn.storagePoolLookupByName(pool).listAllVolumes()

    @retry()
    def volume_allocation(self, volume):
        """Get volume allocation

        :type volume: Volume
            :rtype : Long
        """
        return self.conn.storageVolLookupByKey(volume.uuid).info()[2]

    @retry()
    def volume_path(self, volume):
        return self.conn.storageVolLookupByKey(volume.uuid).path()

    def chunk_render(self, stream, size, fd):
        return fd.read(size)

    @retry(count=2)
    def volume_upload(self, volume, path):
        size = _get_file_size(path)
        with open(path, 'rb') as fd:
            stream = self.conn.newStream(0)
            self.conn.storageVolLookupByKey(volume.uuid).upload(
                stream=stream, offset=0,
                length=size, flags=0)
            stream.sendAll(self.chunk_render, fd)
            stream.finish()

    @retry()
    def volume_delete(self, volume):
        """Delete volume

        :type volume: Volume
            :rtype : None
        """
        self.conn.storageVolLookupByKey(volume.uuid).delete(0)

    @retry()
    def volume_capacity(self, volume):
        """Get volume capacity

        :type volume: Volume
            :rtype : Long
        """
        return self.conn.storageVolLookupByKey(volume.uuid).info()[1]

    @retry()
    def volume_format(self, volume):
        """Get volume format

        :type volume: Volume
            :rtype : String
        """
        xml_desc = ET.fromstring(
            self.conn.storageVolLookupByKey(volume.uuid).XMLDesc(0))
        return xml_desc.find('target/format[@type]').get('type')
