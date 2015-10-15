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

import os
import datetime
from time import sleep
import xml.etree.ElementTree as ET

import ipaddr
import libvirt

from devops.driver.libvirt.libvirt_xml_builder import LibvirtXMLBuilder
from devops.helpers.helpers import _get_file_size
from devops.helpers.retry import retry
from devops.helpers import scancodes
from devops import logger

from django.conf import settings


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

    @property
    def parent(self):
        return self._snapshot.getParent()

    def __repr__(self):
        if not self._repr:
            self._repr = "<{0} {1}/{2}>".format(
                self.__class__.__name__, self.name, self.created)
        return self._repr


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
    def get_capabilities(self):
        """Get host capabilities

        :rtype : ET
        """
        if self.capabilities is None:
            self.capabilities = self.conn.getCapabilities()
        return ET.fromstring(self.capabilities)

    @retry()
    def network_bridge_name(self, network):
        """Get bridge name from UUID

        :type network: Network
            :rtype : String
        """
        return self.conn.networkLookupByUUIDString(network.uuid).bridgeName()

    @retry()
    def network_name(self, network):
        """Get network name from UUID

        :type network: Network
            :rtype : String
        """
        return self.conn.networkLookupByUUIDString(network.uuid).name()

    @retry()
    def network_active(self, network):
        """Check if network is active

        :type network: Network
            :rtype : Boolean
        """
        return self.conn.networkLookupByUUIDString(network.uuid).isActive()

    @retry()
    def node_active(self, node):
        """Check if node is active

        :type node: Node
            :rtype : Boolean
        """
        return self.conn.lookupByUUIDString(node.uuid).isActive()

    @retry()
    def network_exists(self, network):
        """Check if network exists

        :type network: Network
            :rtype : Boolean
        """
        try:
            self.conn.networkLookupByUUIDString(network.uuid)
            return True
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_NETWORK:
                return False
            else:
                raise

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
    def network_define(self, network):
        """Define network

        :type network: Network
            :rtype : None
        """
        ret = self.conn.networkDefineXML(
            self.xml_builder.build_network_xml(network))
        ret.setAutostart(True)
        network.uuid = ret.UUIDString()

    @retry()
    def network_destroy(self, network):
        """Destroy network

        :type network: Network
            :rtype : None
        """
        self.conn.networkLookupByUUIDString(network.uuid).destroy()

    @retry()
    def network_undefine(self, network):
        """Undefine network

        :type network: Network
            :rtype : None
        """
        self.conn.networkLookupByUUIDString(network.uuid).undefine()

    @retry()
    def network_create(self, network):
        """Create network

        :type network: Network
            :rtype : None
        """
        self.conn.networkLookupByUUIDString(network.uuid).create()

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
    def node_list(self):
        # virConnect.listDefinedDomains() only returns stopped domains
        #   https://bugzilla.redhat.com/show_bug.cgi?id=839259
        return [item.name() for item in self.conn.listAllDomains()]

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

        snapshots = self.conn.lookupByUUIDString(node.uuid).listAllSnapshots(0)
        return [Snapshot(snap) for snap in snapshots]

    @retry()
    def node_create_snapshot(self, node, name=None, description=None, disk_only=False, external=False):
        """Create snapshot

        :type description: String
        :type name: String
        :type node: Node
            :rtype : None
        """
        domain = self.conn.lookupByUUIDString(node.uuid)

        # Check wether domain has snapshots
        # If has we must to check snapshot type and use the same
        snap_list = domain.listAllSnapshots(0)
        if len(snap_list) > 0:
            snap_type = self._get_snapshot_type(snap_list[0])
            if external and snap_type == 'internal':
                logger.error("Cannot create external snapshot when internal exists")
                return
            if not external and snap_type == 'external':
                logger.error("Cannot create internal snapshot when external exists")
                return

        if name is not None:
            for snap in snap_list:
                if name == snap.getName():
                    logger.error("Snapshot with name %s already exists" % name)
                    return

        logger.info(domain.state(0))
        xml = self.xml_builder.build_snapshot_xml(name, description, node, domain, disk_only, external)
        logger.info(xml)
        if external and not domain.isActive():
            domain.snapshotCreateXML(xml, 16)
        else:
            domain.snapshotCreateXML(xml)
        logger.info(domain.state(0))

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

    def _get_snapshot_type(self, snapshot):
        """Return snapshot type
        """
        xml_tree = ET.fromstring(snapshot.getXMLDesc())
        snap_state = xml_tree.findall('./state')[0].text
        snap_memory = xml_tree.findall('./memory')[0]
        snap_type = 'internal'
        snap_saved = False
        if snap_memory.get('snapshot') == 'external':
            snap_type = 'external'
        for disk in xml_tree.iter('disk'):
            if disk.get('snapshot') == 'external':
                snap_type = 'external'
        return snap_type

    def _get_snapshot_files(self, snapshot):
        """Return snapshot files
        """
        xml_tree = ET.fromstring(snapshot.getXMLDesc())
        snap_files = []
        for disk in xml_tree.findall('./disks')[0]:
            if disk.get('snapshot') == 'external':
                snap_files.append(disk.findall('source')[0].get('file'))
        snap_memory = xml_tree.findall('./memory')[0]
        if snap_memory.get('file') is not None:
            snap_files.append(snap_memory.get('file'))
        return snap_files

    @retry()
    def node_revert_snapshot(self, node, name=None):
        """Revert snapshot for node

        :type node: Node
        :type name: String
            :rtype : None
        """
        domain = self.conn.lookupByUUIDString(node.uuid)
        snapshot = self._get_snapshot(domain, name)
        #print dir(snapshot)
        #print snapshot.isCurrent()
        #print snapshot.getXMLDesc()
        xml_tree = ET.fromstring(snapshot.getXMLDesc())
        snap_state = xml_tree.findall('state')[0].text
        snap_memory = xml_tree.findall('memory')[0]

        snap_type = self._get_snapshot_type(snapshot)
        if snap_type == 'external':
            snap_saved = True
        else:
            snap_saved = False

#        if snap_type == 'external' and snap_state == 'paused':
        if snap_type == 'external':
            logger.info("Revert external %s %s" % (node.name, snap_state))
            self.conn.restoreFlags(snap_memory.get('file'), flags=4)
            logger.info("Create snapshot disk for changes")
#            self.node_create_snapshot(node, name='revert1', disk_only=True)
            self.node_create_snapshot(node, name='%s-revert' % name, external=True)

        if snap_type == 'internal':
            domain.revertToSnapshot(snapshot, 0)

    @retry()
    def node_delete_all_snapshots(self, node):
        """Delete all snapshots for node

        :type node: Node
        """

        domain = self.conn.lookupByUUIDString(node.uuid)

        # Delete all external snapshots end return
        snap_list = domain.listAllSnapshots(0)
        if len(snap_list) > 0:
            snap_type = self._get_snapshot_type(snap_list[0])
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
        snap_type = self._get_snapshot_type(snapshot)
        #print snapshot.getXMLDesc()
        if snap_type == 'external':
            if snapshot.numChildren() > 0:
                logger.error("With external snapshots you cannot delete snapshot with childrens")
                return

            if domain.isActive():
                logger.error("Cannot delete external snapshot on active domain")
                return

            # Update domain to snapshot state
            xml_tree = ET.fromstring(snapshot.getXMLDesc())
            xml_domain = xml_tree.find('domain')
            self.conn.defineXML(ET.tostring(xml_domain))

            # Delete snapshot files
            for snap_file in self._get_snapshot_files(snapshot):
                print "Delete external snapshot file %s" % snap_file
                if os.path.isfile(snap_file):
                    os.remove(snap_file)
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

    @retry()
    def get_allocated_networks(self):
        """Get list of allocated networks

            :rtype : List
        """
        if self.allocated_networks is None:
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
            self.allocated_networks = allocated_networks
        return self.allocated_networks
