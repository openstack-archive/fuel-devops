# vim: ts=4 sw=4 expandtab
from time import sleep
import libvirt
from src.devops.driver.libvirt.libvirt_xml_builder import LibvirtXMLBuilder
from src.devops.helpers import scancodes
from src.devops.helpers.retry import retry
import xml.etree.ElementTree as ET
import ipaddr
from src.devops.models import Node


class LibvirtException(Exception):
    pass

class LibvirtDriver:
    def __init__(self, name, xml_builder=LibvirtXMLBuilder()):
        self.xml_builder = xml_builder
        libvirt.virInitialize()
        self.conn = libvirt.open(name)
        self.capabilities = None

    def get_capabilities(self):
        if self.capabilities is None:
            self.capabilities = self.conn.getCapabilities()
        return ET.fromstring(self.capabilities)

    @retry()
    def bridge_name(self, network):
        self.conn.networkLookupByUUIDString(network.uuid).bridgeName()

    @retry()
    def create_network(self, network):
        network.uuid = self.conn.networkDefineXML(
            self.xml_builder.build_network_xml(network)
        ).UUID

    @retry()
    def delete_network(self, network):
        self.conn.networkLookupByUUID(network.uuid).destroy()
        self.conn.networkLookupByUUID(network.uuid).undefine()

    @retry()
    def start_network(self, network):
        self.conn.networkLookupByUUIDString(network.uuid).create()

    @retry()
    def stop_network(self, network):
        self.conn.networkLookupByUUIDString(network.uuid).destroy()

    def create_node(self, node):
        """
        :rtype : None
        :type node: Node
        """
        emulator = self.get_capabilities(
        ).find(
            'guest/arch[@name="{0:>s}"]/domain[@type="{1:>s}"]/emulator'.format(
                node.architecture, node.hypervisor)).text
        node_xml = self.xml_builder.build_node_xml(node, emulator)
        self.uuid = self.conn.createXML(node_xml, 0).UUID()

    def delete_node(self, node):
        self.conn.lookupByUUID(node.uuid).destroy()
        self.conn.lookupByUUID(node.uuid).undefine()

    def get_vnc_port(self, node):
        xml_desc = ET.fromstring(self.conn.lookupByUUID(node.uuid).XMLDesc(0))
        vnc_element = xml_desc.find('devices/graphics[@type="vnc"][@port]')
        if vnc_element:
            return vnc_element.get('port')

    def start_node(self, node):
        self.conn.lookupByUUID(node.uuid).create()

    def stop_node(self, node):
        self.destroy_node(node)

    def reset_node(self, node):
        self.conn.lookupByUUID(node.uuid).reset()

    def reboot_node(self, node):
        self.conn.lookupByUUID(node.uuid).reboot()

    def suspend_node(self, node):
        self.conn.lookupByUUID(node.uuid).suspend()

    def resume_node(self, node):
        self.conn.lookupByUUID(node.uuid).resume()

    def shutdown_node(self, node):
        self.conn.lookupByUUID(node.uuid).shutdown()

    def destroy_node(self, node):
        self.conn.lookupByUUID(node.uuid).destroy()

    def get_node_snapshots(self, node):
        self.conn.lookupByUUID(node.uuid).snapshotListNames(0)

    def create_snapshot(self, node, name=None, description=None):
        xml =self.xml_builder.build_snapshot_xml(name, description)
        self.conn.lookupByUUID(node.uuid).snapshotCreateXML(xml)

    def _get_snapshot(self, domain, name):
        if name is None:
            return domain.snapshotCurrent()
        else:
            return domain.snapshotLookupByName(name, 0)

    def revert_snapshot(self, node, name=None):
        domain = self.conn.lookupByUUID(node.uuid)
        snapshot = self._get_snapshot(domain, name)
        domain.revertToSnapshot(snapshot,0)

    def delete_snapshot(self, node, name=None):
        domain = self.conn.lookupByUUID(node.uuid)
        snapshot = self._get_snapshot(domain, name)
        snapshot.delete(0)

    def send_keys_to_node(self, node, keys):
        keys = scancodes.from_string(str(keys))
        for key_codes in keys:
            if isinstance(key_codes[0], str):
                if key_codes[0] == 'wait':
                    sleep(1)
                continue
            self.conn.lookupByUUID(node.uuid).sendKey(0, 0, key_codes, len(key_codes), 0, 0)

    def create_volume(self, volume, libvirt_pool='default'):
        libvirt_pool = self.conn.storagePoolLookupByName(libvirt_pool)
        libvirt_volume = libvirt_pool.createXML(self.xml_builder.build_volume_xml(volume))
        volume.uuid = libvirt_volume.key()

    def _get_file_size(self, file):
        current = file.tell()
        try:
            file.seek(0, 2)
            size = file.tell()
        finally:
            file.seek(current)
        return size

    def upload_volume(self, volume, path):
        with open(path, 'rb') as f:
            self.conn.storageVolLookupByKey(volume.uuid).upload(
                stream = f, offset = 0,
                length = self._get_file_size(f), flags = 0)

    def delete_disk(self, disk):
        self.conn.storageVolLookupByKey(disk.uuid)

    def get_allocated_networks(self):
        allocated_networks =[]
        for network_name in self.conn.listDefinedNetworks():
            et = ET.fromstring(self.conn.networkLookupByName(network_name).XMLDesc())
            ip = et.find('ip[@address]')
            if ip:
                address = ip.get('address')
                prefix_or_netmask = ip.get('prefix') or ip.get('netmask')
                allocated_networks.append(ipaddr.IPNetwork(
                    "{0:>s}/{1:>s}".format(address, prefix_or_netmask)))
        return allocated_networks


