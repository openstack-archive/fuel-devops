# vim: ts=4 sw=4 expandtab
from time import sleep
import libvirt
from src.devops.driver.libvirt.libvirt_xml_builder import LibvirtXMLBuilder
from src.devops.helpers import scancodes
from src.devops.helpers.retry import retry
import xml.etree.ElementTree as ET
import ipaddr
from src.devops.models import Node, Volume


class LibvirtDriver:
    def __init__(self, name, xml_builder=LibvirtXMLBuilder()):
        self.xml_builder = xml_builder
        libvirt.virInitialize()
        self.conn = libvirt.open(name)
        self.capabilities = None

    @retry()
    def get_capabilities(self):
        """
        :rtype : ET
        """
        if self.capabilities is None:
            self.capabilities = self.conn.getCapabilities()
        return ET.fromstring(self.capabilities)

    @retry()
    def network_bridge_name(self, network):
        """
        :rtype : None
        """
        self.conn.networkLookupByUUIDString(network.uuid).bridgeName()

    @retry()
    def network_create(self, network):
        """
        :rtype : None
        """
        network.uuid = self.conn.networkDefineXML(
            self.xml_builder.build_network_xml(network)
        ).UUID()

    @retry()
    def network_delete(self, network):
        """
        :rtype : None
        """
        self.conn.networkLookupByUUID(network.uuid).destroy()
        self.conn.networkLookupByUUID(network.uuid).undefine()

    @retry()
    def network_start(self, network):
        """
        :rtype : None
        """
        self.conn.networkLookupByUUIDString(network.uuid).create()

    @retry()
    def network_stop(self, network):
        """
        :rtype : None
        """
        self.conn.networkLookupByUUIDString(network.uuid).destroy()

    @retry()
    def node_create(self, node):
        """
        :type node: Node
        :rtype : None
        """
        emulator = self.get_capabilities(
        ).find(
            'guest/arch[@name="{0:>s}"]/domain[@type="{1:>s}"]/emulator'.format(
                node.architecture, node.hypervisor)).text
        node_xml = self.xml_builder.build_node_xml(node, emulator)
        self.uuid = self.conn.createXML(node_xml, 0).UUID()

    @retry()
    def node_delete(self, node):
        """
        :type node: Node
        :rtype : None
        """
        self.conn.lookupByUUID(node.uuid).destroy()
        self.conn.lookupByUUID(node.uuid).undefine()

    @retry()
    def node_get_vnc_port(self, node):
        """
        :type node: Node
        :rtype : String
        """
        xml_desc = ET.fromstring(self.conn.lookupByUUID(node.uuid).XMLDesc(0))
        vnc_element = xml_desc.find('devices/graphics[@type="vnc"][@port]')
        if vnc_element:
            return vnc_element.get('port')

    @retry()
    def node_start(self, node):
        """
        :type node: Node
        :rtype : None
        """
        self.conn.lookupByUUID(node.uuid).create()

    @retry()
    def node_reset(self, node):
        """
        :type node: Node
        :rtype : None
        """
        self.conn.lookupByUUID(node.uuid).reset()

    @retry()
    def node_reboot(self, node):
        """
        :type node: Node
        :rtype : None
        """
        self.conn.lookupByUUID(node.uuid).reboot()

    @retry()
    def node_suspend(self, node):
        """
        :type node: Node
        :rtype : None
        """
        self.conn.lookupByUUID(node.uuid).suspend()

    @retry()
    def node_resume(self, node):
        """
        :type node: Node
        :rtype : None
        """
        self.conn.lookupByUUID(node.uuid).resume()

    @retry()
    def node_shutdown(self, node):
        """
        :type node: Node
        :rtype : None
        """
        self.conn.lookupByUUID(node.uuid).shutdown()

    @retry()
    def node_destroy(self, node):
        """
        :type node: Node
        :rtype : None
        """
        self.conn.lookupByUUID(node.uuid).destroy()

#    @retry()
    def node_get_snapshots(self, node):
        """
        :rtype : List
        :type node: Node
        """
        return self.conn.lookupByUUID(node.uuid).snapshotListNames(0)

    @retry()
    def node_create_snapshot(self, node, name=None, description=None):
        """
        :type description: String
        :type name: String
        :type node: Node
        :rtype : None
        """
        xml = self.xml_builder.build_snapshot_xml(name, description)
        self.conn.lookupByUUID(node.uuid).snapshotCreateXML(xml)

    @retry()
    def _get_snapshot(self, domain, name):
        """
        :type name: String
        :rtype : libvirt.virDomainSnapshot
        """
        if name is None:
            return domain.snapshotCurrent()
        else:
            return domain.snapshotLookupByName(name, 0)

    @retry()
    def node_revert_snapshot(self, node, name=None):
        """
        :type node: Node
        :type name: String
        :rtype : None
        """
        domain = self.conn.lookupByUUID(node.uuid)
        snapshot = self._get_snapshot(domain, name)
        domain.revertToSnapshot(snapshot, 0)

    @retry()
    def node_delete_snapshot(self, node, name=None):
        """
        :type node: Node
        :type name: String
        """
        domain = self.conn.lookupByUUID(node.uuid)
        snapshot = self._get_snapshot(domain, name)
        snapshot.delete(0)

    @retry()
    def node_send_keys(self, node, keys):
        """
        :rtype : None
        :type node: Node
        """

        keys = scancodes.from_string(str(keys))
        for key_codes in keys:
            if isinstance(key_codes[0], str):
                if key_codes[0] == 'wait':
                    sleep(1)
                continue
            self.conn.lookupByUUID(node.uuid).sendKey(0, 0, key_codes,
                len(key_codes), 0, 0)

    @retry()
    def volume_create(self, volume, pool='default'):
        """
        :type volume: Volume
        :type pool: String
        :rtype : None
        """
        libvirt_volume = self.conn.storagePoolLookupByName(pool).createXML(
            self.xml_builder.build_volume_xml(volume))
        volume.uuid = libvirt_volume.key()

    def _get_file_size(self, file):
        """
        :type file: file
        :rtype : int
        """
        current = file.tell()
        try:
            file.seek(0, 2)
            size = file.tell()
        finally:
            file.seek(current)
        return size

    @retry(count=2)
    def volume_upload(self, volume, path):
        with open(path, 'rb') as f:
            self.conn.storageVolLookupByKey(volume.uuid).upload(
                stream=f, offset=0,
                length=self._get_file_size(f), flags=0)

    @retry()
    def volume_delete(self, volume):
        """
        :type volume: Volume
        :rtype : None
        """
        self.conn.storageVolLookupByKey(volume.uuid)

    @retry()
    def get_allocated_networks(self):
        """
        :rtype : List
        """
        allocated_networks = []
        for network_name in self.conn.listDefinedNetworks():
            et = ET.fromstring(
                self.conn.networkLookupByName(network_name).XMLDesc())
            ip = et.find('ip[@address]')
            if ip:
                address = ip.get('address')
                prefix_or_netmask = ip.get('prefix') or ip.get('netmask')
                allocated_networks.append(ipaddr.IPNetwork(
                    "{0:>s}/{1:>s}".format(address, prefix_or_netmask)))
        return allocated_networks
