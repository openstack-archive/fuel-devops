from collections import deque
from ipaddr import IPNetwork
from xmlbuilder import XMLBuilder
from src.devops.models import Node


class LibvirtXMLBuilder:

    NAME_SIZE = 80

    def get_name(self, *args):
        name = '_'.join(list(args))
        if len(name) > self.NAME_SIZE:
            hash_str = str(hash(name))
            name=hash_str+name[len(name)-self.NAME_SIZE+len(hash_str):]
        return  name

    def find(self, p, seq):
        for item in seq:
            if p(item):
                return item
        return None

    def build_network_xml(self, network):
        """
        :type network: Network
        :rtype : String
        """
        network_xml = XMLBuilder('network')
        network_xml.name(self.get_name(network.environment.name, network.name))
        if not (network.forward is None):
            network_xml.forward(mode=network.forward)
        if not (network.ip_network is None):
            ip_network = IPNetwork(network.ip_network)
            with network_xml.ip(
                address=str(ip_network.network),
                prefix=str(network.ip_network.prefixlen)):
                if network.has_pxe_server:
                    network_xml.tftp(root=network.tftp_root_dir)
                if network.has_dhcp_server:
                    with network_xml.dhcp:
                        allowed_addresses = list(network.ip_addresses)[2: - 2]
                        network_xml.range(start=str(start), end=str(end))
                        for interface in network.interfaces:
                            address = self.find(
                                lambda ip: ip in allowed_addresses,
                                interface.ip_addresses
                            )
                            if address and interface.mac_address:
                                network_xml.host(
                                    mac=str(interface.mac_address),
                                    ip=str(address),
                                    name=interface.node.name
                                )
                        if network.pxe:
                            network_xml.bootp(file="pxelinux.0")

        return str(network_xml)

    def build_volume_xml(self, volume, backing_store_path=None):
        """
        :type volume: Volume
        :type backing_store_path: String
        :rtype : String
        """
        volume_xml = XMLBuilder('volume')
        volume_xml.name(volume.name)
        volume_xml.capacity(volume.capacity)
        with volume_xml.target:
            volume_xml.format(type=volume.format)
        if volume.backing_store:
            with volume_xml.backing_store:
                volume_xml.path = backing_store_path
                volume_xml.format = volume.backing_store.format
        return str(volume_xml)

    def build_snapshot_xml(self, name=None, description=None):
        """
        :rtype : String
        :type name: String
        :type description: String
        """
        xml_builder = XMLBuilder('domainsnapshot')
        if not (name is None):
            xml_builder.name(name)
        if not (description is None):
            xml_builder.description(description)

    def build_node_xml(self, node, emulator):
        """
        :rtype : String
        :type node: Node
        """
        node_xml = XMLBuilder("domain", type=node.hypervisor)
        node_xml.name(node.name)
        node_xml.vcpu(str(node.vcpu))
        node_xml.memory(str(node.memory), unit='MiB')

        with node_xml.os:
            node_xml.type(node.os_type, arch=node.architecture)
            for boot_dev in node.boot:
                node_xml.boot(dev=boot_dev)

        serial_disk_names = deque(
            ['sd' + c for c in list('abcdefghijklmnopqrstuvwxyz')])

        def disk_name():
            return serial_disk_names.popleft()

        with node_xml.devices:
            node_xml.emulator(emulator)

            if len(node.disks) > 0:
                node_xml.controller(type="ide")

            for disk in node.disks:
                with node_xml.disk(type="file", device="disk"):
#                    node_xml.driver(
#                        name="qemu", type=disk.format,
#                        cache="unsafe")
                    node_xml.source(file=disk.path)
                    node_xml.target(dev=disk_name(disk.bus), bus=disk.bus)

            if node.cdrom:
                with node_xml.disk(type="file", device="cdrom"):
#                    node_xml.driver(name="qemu", type="raw")
                    node_xml.source(file=node.cdrom.isopath)
                    node_xml.target(
                        dev=disk_name(node.cdrom.bus),
                        bus=node.cdrom.bus)

            for interface in node.interfaces:
                with node_xml.interface(type=interface.type):
                    node_xml.source(network=interface.network.id)
                    if not (interface.type is None):
                        node_xml.model(type=interface.type)

            if node.has_vnc:
                node_xml.graphics(type='vnc', listen='0.0.0.0', autoport='yes')

        return str(node_xml)
