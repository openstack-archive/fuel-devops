import json
from ipaddr import IPNetwork, IPAddress
from xmlbuilder import XMLBuilder


class LibvirtXMLBuilder(object):
    def __init__(self, driver):
        super(LibvirtXMLBuilder, self).__init__()
        self.driver = driver

    NAME_SIZE = 80

    def _get_name(self, *args):
        name = '_'.join(list(args))
        if len(name) > self.NAME_SIZE:
            hash_str = str(hash(name))
            name = hash_str + name[len(name) - self.NAME_SIZE + len(hash_str):]
        return  name

    def build_network_xml(self, network):
        """
        :type network: Network
        :rtype : String
        """
        network_xml = XMLBuilder('network')
        network_xml.name(self._get_name(
            network.environment and network.environment.name or '',
            network.name))
        if not (network.forward is None):
            network_xml.forward(mode=network.forward)
        if not (network.ip_network is None):
            ip_network = IPNetwork(network.ip_network)
            with network_xml.ip(
                address=str(ip_network[1]),
                prefix=str(ip_network.prefixlen)):
                if network.has_pxe_server:
                    network_xml.tftp(root=network.tftp_root_dir)
                if network.has_dhcp_server:
                    with network_xml.dhcp:
                        network_xml.range(start=str(network.ip_pool_start),
                            end=str(network.ip_pool_end))
                        for interface in network.interfaces:
                            for address in interface.addresses:
                                if IPAddress(address.ip_address) in ip_network:
                                    network_xml.host(
                                        mac=str(interface.mac_address),
                                        ip=str(address.ip_address),
                                        name=interface.node.name
                                    )
                        if network.has_pxe_server:
                            network_xml.bootp(file="pxelinux.0")

        return str(network_xml)

    def build_volume_xml(self, volume):
        """
        :type volume: Volume
        :rtype : String
        """
        volume_xml = XMLBuilder('volume')
        volume_xml.name(
            self._get_name(volume.environment and volume.environment.name or '',
                volume.name))
        volume_xml.capacity(str(volume.capacity))
        with volume_xml.target:
            volume_xml.format(type=volume.format)
        if volume.backing_store is not None:
            with volume_xml.backingStore:
                volume_xml.path(self.driver.volume_path(volume.backing_store))
                volume_xml.format(type=volume.backing_store.format)
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
        return str(xml_builder)

    def _build_disk_device(self, device_xml, disk_device):
        with device_xml.disk(type=disk_device.type, device=disk_device.device):
            #https://bugs.launchpad.net/ubuntu/+source/qemu-kvm/+bug/741887
            device_xml.driver(type=disk_device.volume.format, cache="unsafe")
            device_xml.source(file=self.driver.volume_path(disk_device.volume))
            device_xml.target(dev=disk_device.target_dev, bus=disk_device.bus)

    def _build_interface_device(self, device_xml, interface):
        if interface.type != 'network':
            raise NotImplementedError()
        with device_xml.interface(type=interface.type):
            device_xml.mac(address=interface.mac_address)
            device_xml.source(
                network=self.driver.network_name(interface.network))
            if not (interface.type is None):
                device_xml.model(type=interface.model)

    def build_node_xml(self, node, emulator):
        """
        :rtype : String
        :type node: Node
        """
        node_xml = XMLBuilder("domain", type=node.hypervisor)
        node_xml.name(
            self._get_name(node.environment and node.environment.name or '',
                node.name))
        node_xml.vcpu(str(node.vcpu))
        node_xml.memory(str(node.memory*1024), unit='KiB')

        with node_xml.os:
            node_xml.type(node.os_type, arch=node.architecture)
            for boot_dev in json.loads(node.boot):
                node_xml.boot(dev=boot_dev)

        with node_xml.devices:
            node_xml.emulator(emulator)
            if node.has_vnc:
                node_xml.graphics(type='vnc', listen='0.0.0.0', autoport='yes')

            for disk_device in node.disk_devices:
                self._build_disk_device(node_xml, disk_device)
            for interface in node.interfaces:
                self._build_interface_device(node_xml, interface)
        return str(node_xml)
