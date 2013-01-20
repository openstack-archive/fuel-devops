# vim: ts=4 sw=4 expandtab
from time import sleep
import libvirt
from devops.driver.libvirt.libvirt_xml_builder import LibvirtXMLBuilder
from devops.helpers import scancodes
from devops.helpers.retry import retry
import xml.etree.ElementTree as ET
import ipaddr


class LibvirtDriver(object):
    def __init__(self, connection_string=""):
        libvirt.virInitialize()
        self.conn = libvirt.open(connection_string)
        self.xml_builder = LibvirtXMLBuilder(self)
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
        :type network: Network
        :rtype : String
        """
        return self.conn.networkLookupByUUIDString(network.uuid).bridgeName()

    @retry()
    def network_name(self, network):
        """
        :type network: Network
        :rtype : String
        """
        return self.conn.networkLookupByUUIDString(network.uuid).name()


    @retry()
    def network_active(self, network):
        """
        :type network: Network
        :rtype : Boolean
        """
        return self.conn.networkLookupByUUIDString(network.uuid).isActive()

    @retry()
    def node_active(self, node):
        """
        :type node: Node
        :rtype : Boolean
        """
        return self.conn.networkLookupByUUIDString(node.uuid).isActive()


    @retry()
    def network_exists(self, network):
        """
        :type network: Network
        :rtype : Boolean
        """
        try:
            self.conn.networkLookupByUUIDString(network.uuid)
            return True
        except libvirt.libvirtError, e:
            if e.message ==  'virNetworkLookupByUUIDString() failed':
                return False
        raise

    @retry()
    def node_exists(self, node):
        """
        :type node: Node
        :rtype : Boolean
        """
        try:
            self.conn.lookupByUUIDString(node.uuid)
            return True
        except libvirt.libvirtError, e:
            if e.message  ==  'virDomainLookupByUUIDString() failed':
                return False
        raise

    @retry()
    def volume_exists(self, volume):
        """
        :type volume: Volume
        :rtype : Boolean
        """
        try:
            self.conn.storageVolLookupByKey(volume.uuid)
            return True
        except libvirt.libvirtError, e:
            if e.message ==  'virStorageVolLookupByKey() failed':
                return False
        raise

    @retry()
    def network_define(self, network):
        """
        :rtype : None
        """
        network.uuid = self.conn.networkDefineXML(
            self.xml_builder.build_network_xml(network)
        ).UUIDString()

    @retry()
    def network_destroy(self, network):
        """
        :rtype : None
        """
        self.conn.networkLookupByUUIDString(network.uuid).destroy()

    @retry()
    def network_undefine(self, network):
        """
        :rtype : None
        """
        self.conn.networkLookupByUUIDString(network.uuid).undefine()

    @retry()
    def network_create(self, network):
        """
        :rtype : None
        """
        self.conn.networkLookupByUUIDString(network.uuid).create()

    @retry()
    def network_destroy(self, network):
        """
        :rtype : None
        """
        self.conn.networkLookupByUUIDString(network.uuid).destroy()

    @retry()
    def node_define(self, node):
        """
        :type node: Node
        :rtype : None
        """
        emulator = self.get_capabilities(
        ).find(
            'guest/arch[@name="{0:>s}"]/domain[@type="{1:>s}"]/emulator'.format(
                node.architecture, node.hypervisor)).text
        node_xml = self.xml_builder.build_node_xml(node, emulator)
        for network in node.networks:
            print network
            if not self.network_active(network):
                self.network_create(network)
        print node_xml
        self.uuid = self.conn.createXML(node_xml, 0).UUIDString()

    @retry()
    def node_destroy(self, node):
        """
        :type node: Node
        :rtype : None
        """
        self.conn.lookupByUUIDString(node.uuid).destroy()

    @retry()
    def node_undefine(self, node):
        """
        :type node: Node
        :rtype : None
        """
        self.conn.lookupByUUIDString(node.uuid).undefine()

    @retry()
    def node_get_vnc_port(self, node):
        """
        :type node: Node
        :rtype : String
        """
        xml_desc = ET.fromstring(self.conn.lookupByUUIDString(node.uuid).XMLDesc(0))
        vnc_element = xml_desc.find('devices/graphics[@type="vnc"][@port]')
        if vnc_element:
            return vnc_element.get('port')

    @retry()
    def node_create(self, node):
        """
        :type node: Node
        :rtype : None
        """
        self.conn.lookupByUUIDString(node.uuid).create()

    @retry()
    def node_reset(self, node):
        """
        :type node: Node
        :rtype : None
        """
        self.conn.lookupByUUIDString(node.uuid).reset()

    @retry()
    def node_reboot(self, node):
        """
        :type node: Node
        :rtype : None
        """
        self.conn.lookupByUUIDString(node.uuid).reboot()

    @retry()
    def node_suspend(self, node):
        """
        :type node: Node
        :rtype : None
        """
        self.conn.lookupByUUIDString(node.uuid).suspend()

    @retry()
    def node_resume(self, node):
        """
        :type node: Node
        :rtype : None
        """
        self.conn.lookupByUUIDString(node.uuid).resume()

    @retry()
    def node_shutdown(self, node):
        """
        :type node: Node
        :rtype : None
        """
        self.conn.lookupByUUIDString(node.uuid).shutdown()

    @retry()
    def node_destroy(self, node):
        """
        :type node: Node
        :rtype : None
        """
        self.conn.lookupByUUIDString(node.uuid).destroy()

#    @retry()
    def node_get_snapshots(self, node):
        """
        :rtype : List
        :type node: Node
        """
        return self.conn.lookupByUUIDString(node.uuid).snapshotListNames(0)

    @retry()
    def node_create_snapshot(self, node, name=None, description=None):
        """
        :type description: String
        :type name: String
        :type node: Node
        :rtype : None
        """
        xml = self.xml_builder.build_snapshot_xml(name, description)
        self.conn.lookupByUUIDString(node.uuid).snapshotCreateXML(xml)

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
        domain = self.conn.lookupByUUIDString(node.uuid)
        snapshot = self._get_snapshot(domain, name)
        domain.revertToSnapshot(snapshot, 0)

    @retry()
    def node_delete_snapshot(self, node, name=None):
        """
        :type node: Node
        :type name: String
        """
        domain = self.conn.lookupByUUIDString(node.uuid)
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
            self.conn.lookupByUUIDString(node.uuid).sendKey(0, 0, key_codes,
                len(key_codes), 0, 0)

    @retry()
    def volume_define(self, volume, pool='default'):
        """
        :type volume: Volume
        :type pool: String
        :rtype : None
        """
        libvirt_volume = self.conn.storagePoolLookupByName(pool).createXML(
            self.xml_builder.build_volume_xml(volume))
        volume.uuid = libvirt_volume.key()

    @retry()
    def volume_path(self, volume):
        return self.conn.storageVolLookupByKey(volume.uuid).path()

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
        self.conn.storageVolLookupByKey(volume.uuid).delete(0)

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
