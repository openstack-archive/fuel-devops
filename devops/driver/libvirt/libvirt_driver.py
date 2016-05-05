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

from __future__ import division
import datetime
import os
from time import sleep
import xml.etree.ElementTree as ET

import libvirt
from netaddr import IPNetwork

from devops.driver.libvirt.libvirt_xml_builder import LibvirtXMLBuilder
from devops.error import DevopsError
from devops.helpers.helpers import _get_file_size
from devops.helpers.retry import retry
from devops.helpers import scancodes
from devops import logger

from django.conf import settings


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
        cpu = snapshot_xmltree.findall('./domain/cpu')
        if cpu and 'mode' in cpu[0].attrib:
            cpu_mode = cpu[0].get('mode')
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


class DevopsDriver(object):
    def __init__(self,
                 connection_string="qemu:///system",
                 storage_pool_name="default",
                 stp=True, hpet=True, use_host_cpu=True, enable_acpi=False):
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
        self.storage_pool_name = storage_pool_name
        self.reboot_timeout = None
        self.use_host_cpu = use_host_cpu
        self.enable_acpi = enable_acpi
        self.use_hugepages = settings.USE_HUGEPAGES

        if settings.VNC_PASSWORD:
            self.vnc_password = settings.VNC_PASSWORD

        if settings.REBOOT_TIMEOUT:
            self.reboot_timeout = settings.REBOOT_TIMEOUT

    def __del__(self):
        self.conn.close()

    def _get_name(self, *kwargs):
        return self.xml_builder._get_name(*kwargs)

    def get_libvirt_version(self):
        return self.conn.getLibVersion()

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
            self.xml_builder.build_network_xml(
                network, br_prefix=settings.LIBVIRT_BR_PREFIX))
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
        try:
            network = self.conn.networkLookupByUUIDString(network.uuid)
        except libvirt.libvirtError:
            logger.error("Network not found by UUID: {}".format(network.uuid))
            return
        return network.undefine()

    @retry()
    def network_create(self, network):
        """Create network

        :type network: Network
            :rtype : None
        """
        self.conn.networkLookupByUUIDString(network.uuid).create()

    @retry()
    def network_filter_define(self, network):
        """Define network filter"""
        return self.conn.nwfilterDefineXML(
            self.xml_builder.build_network_filter(network))

    def get_network_filter(self, network):
        network_name = "{}_{}".format(network.environment.name, network.name)
        try:
            return self.conn.nwfilterLookupByName(network_name)
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_NWFILTER:
                return None
            else:
                raise

    @retry()
    def network_filter_undefine(self, network):
        """Undefine network filter"""
        nwfilter = self.get_network_filter(network)
        if nwfilter is not None:
            nwfilter.undefine()

    @retry()
    def network_block_status(self, network):
        """Return network block status"""
        nwfilter = self.get_network_filter(network)
        if nwfilter is None:
            return False
        filter_xml = ET.fromstring(nwfilter.XMLDesc())
        return filter_xml.find('./rule') is not None

    @retry()
    def network_block(self, network):
        """Block all traffic in network"""
        nwfilter = self.get_network_filter(network)
        if nwfilter is None:
            raise DevopsError(
                "Unable to block network {0}: nwfilter not found!"
                .format(network.name))
        filter_xml = ET.fromstring(nwfilter.XMLDesc())
        rule = ET.Element(
            'rule',
            {'action': 'drop', 'direction': "inout", 'priority': '-1000'})
        rule.append(ET.Element('all'))
        filter_xml.find('.').append(rule)
        self.conn.nwfilterDefineXML(ET.tostring(filter_xml))

    @retry()
    def network_unblock(self, network):
        """Unblock all traffic in network"""
        nwfilter = self.get_network_filter(network)
        if nwfilter is None:
            raise DevopsError(
                "Unable to unblock network {0}: nwfilter not found!"
                .format(network.name))
        filter_xml = ET.fromstring(nwfilter.XMLDesc())
        filter_xml.find('.').remove(filter_xml.find('./rule'))
        self.conn.nwfilterDefineXML(ET.tostring(filter_xml))

    @retry()
    def interface_filter_define(self, interface):
        self.conn.nwfilterDefineXML(
            self.xml_builder.build_interface_filter(interface))

    def get_interface_filter(self, interface):
        iface_name = "{}_{}_{}".format(
            interface.network.environment.name,
            interface.network.name,
            interface.mac_address)
        try:
            return self.conn.nwfilterLookupByName(iface_name)
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_NWFILTER:
                return None
            else:
                raise

    @retry()
    def interface_filter_undefine(self, interface):
        """Undefine interface filter"""
        nwfilter = self.get_interface_filter(interface)
        if nwfilter is not None:
            nwfilter.undefine()

    @retry()
    def interface_block_status(self, interface):
        """Return block status of interface"""
        nwfilter = self.get_interface_filter(interface)
        if nwfilter is None:
            return False
        filter_xml = ET.fromstring(nwfilter.XMLDesc())
        return filter_xml.find('./rule') is not None

    @retry()
    def interface_block(self, interface):
        """Block traffic on interface"""
        nwfilter = self.get_interface_filter(interface)
        if nwfilter is None:
            raise DevopsError(
                "Unable to block interface {0}_{1} on node {2}: nwfilter not"
                " found!".format(interface.name, interface.mac_address,
                                 interface.node.name))
        filter_xml = ET.fromstring(nwfilter.XMLDesc())
        rule = ET.Element(
            'rule',
            {'action': 'drop', 'direction': "inout", 'priority': '-950'})
        rule.append(ET.Element('all'))
        filter_xml.find('.').append(rule)
        self.conn.nwfilterDefineXML(ET.tostring(filter_xml))

    @retry()
    def interface_unblock(self, interface):
        """Unblock traffic on interface"""
        nwfilter = self.get_interface_filter(interface)
        if nwfilter is None:
            raise DevopsError(
                "Unable to unblock interface {0}_{1} on node {2}: nwfilter not"
                " found!".format(interface.name, interface.mac_address,
                                 interface.node.name))
        filter_xml = ET.fromstring(nwfilter.XMLDesc())
        filter_xml.find('.').remove(filter_xml.find('./rule'))
        self.conn.nwfilterDefineXML(ET.tostring(filter_xml))

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

        # NUMA nodes
        # TODO(ddmitriev): pass 'numa' structure from the YAML template
        # for fuel-devops-3.0 instead of calculating parameters here.
        numa_nodes = settings.HARDWARE["numa_nodes"]
        numa = []
        if numa_nodes:
            cpus_per_numa = node.vcpu // numa_nodes
            if cpus_per_numa * numa_nodes != node.vcpu:
                raise DevopsError(
                    "NUMA_NODES={0} is not a multiple of the number of CPU={1}"
                    " for node '{2}'".format(numa_nodes, node.vcpu, node.name))

            memory_per_numa = (node.memory * 1024) // numa_nodes
            if memory_per_numa * numa_nodes != (node.memory * 1024):
                raise DevopsError(
                    "NUMA_NODES={0} is not a multiple of the amount of "
                    "MEMORY={1} for node '{2}'".format(numa_nodes,
                                                       node.memory,
                                                       node.name))
            for x in range(numa_nodes):
                # List of cpu IDs for the numa node
                cpus = range(x * cpus_per_numa, (x + 1) * cpus_per_numa)
                cell = {
                    'cpus': ','.join(map(str, cpus)),
                    'memory': memory_per_numa,
                }
                numa.append(cell)

        node_xml = self.xml_builder.build_node_xml(
            node, emulator, numa, if_prefix=settings.LIBVIRT_IF_PREFIX)
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
        try:
            domain = self.conn.lookupByUUIDString(node.uuid)
        except libvirt.libvirtError:
            logger.error("Domain not found by UUID: {}".format(node.uuid))
            return

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

    @retry()
    def get_allocated_networks(self, all_networks=False):
        """Get list of allocated networks

            :rtype : List
        """
        allocated_networks = []

        if all_networks:  # Get stopped and started libvirt networks
            network_names = [x.name() for x in self.conn.listAllNetworks()]
        else:             # Get only started libvirt networks
            network_names = self.conn.listNetworks()

        for network_name in network_names:
            et = ET.fromstring(
                self.conn.networkLookupByName(network_name).XMLDesc(0))
            ip = et.find('ip[@address]')
            if ip is not None:
                address = ip.get('address')
                prefix_or_netmask = ip.get('prefix') or ip.get('netmask')
                allocated_networks.append(IPNetwork(
                    "{0:>s}/{1:>s}".format(address, prefix_or_netmask)))
        return allocated_networks
