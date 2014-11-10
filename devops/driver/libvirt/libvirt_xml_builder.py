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

import json
import uuid

from ipaddr import IPAddress
from ipaddr import IPNetwork
from xmlbuilder import XMLBuilder


class LibvirtXMLBuilder(object):
    def __init__(self, driver):
        super(LibvirtXMLBuilder, self).__init__()
        self.driver = driver

    NAME_SIZE = 80

    def _get_name(self, *args):
        name = '_'.join(filter(None, list(args)))
        if len(name) > self.NAME_SIZE:
            hash_str = str(hash(name))
            name = hash_str + name[len(name) - self.NAME_SIZE + len(hash_str):]
        return name

    def _build_network_xml(self, network):
        """Generate network XML

        :type network: Network
            :rtype : String
        """
        network_xml = XMLBuilder('network')
        network_xml.name(self._get_name(
            network.environment and network.environment.name or '',
            network.name))

        stp_val = 'off'
        if self.driver.stp:
            stp_val = 'on'
        network_xml.bridge(
            name="fuelbr{0}".format(network.id),
            stp=stp_val, delay="0")

        if network.forward is not None:
            network_xml.forward(mode=network.forward)
        if network.ip_network is not None:
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

        return network_xml

    def _build_bridge_network_xml(self, network):
        """Generate bridged network XML

        :type network: Network
            :rtype : String
        """
        network_xml = XMLBuilder('network')
        network_xml.name(self._get_name(
            network.environment and network.environment.name or '',
            network.name))

        network_xml.forward(mode=network.forward)
        if network.target_dev is None:
            network_xml.bridge(name="dobr{0}".format(network.id))
        else:
            network_xml.bridge(name=network.target_dev)

        return network_xml

    def build_network_xml(self, network):
        """Generate network XML

        :type network: Network
            :rtype : String
        """
        if network.forward == 'bridge':
            network_xml = self._build_bridge_network_xml(network)
        else:
            network_xml = self._build_network_xml(network)

        return str(network_xml)

    def build_volume_xml(self, volume):
        """Generate volume XML

        :type volume: Volume
            :rtype : String
        """
        volume_xml = XMLBuilder('volume')
        volume_xml.name(
            self._get_name(
                volume.environment and volume.environment.name or '',
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
        """Generate snapshot XML

        :rtype : String
        :type name: String
        :type description: String
        """
        xml_builder = XMLBuilder('domainsnapshot')
        if name is not None:
            xml_builder.name(name)
        if description is not None:
            xml_builder.description(description)
        return str(xml_builder)

    def _build_disk_device(self, device_xml, disk_device):
        """Build xml for disk

        :param device_xml: XMLBuilder
        :param disk_device: DiskDevice
        """

        with device_xml.disk(type=disk_device.type, device=disk_device.device):
            # https://bugs.launchpad.net/ubuntu/+source/qemu-kvm/+bug/741887
            device_xml.driver(type=disk_device.volume.format, cache="unsafe")
            device_xml.source(file=self.driver.volume_path(disk_device.volume))
            if disk_device.bus == 'usb':
                device_xml.target(
                    dev=disk_device.target_dev,
                    bus=disk_device.bus,
                    removable='on')
                device_xml.readonly()
            else:
                device_xml.target(
                    dev=disk_device.target_dev,
                    bus=disk_device.bus)
            device_xml.serial(''.join(uuid.uuid4().hex))

    def _build_interface_device(self, device_xml, interface):
        """Build xml for interface

        :param device_xml: XMLBuilder
        :param interface: Network
        """

        if interface.type != 'network':
            raise NotImplementedError(
                message='Interface types different from network are not '
                        'implemented yet')
        with device_xml.interface(type=interface.type):
            device_xml.mac(address=interface.mac_address)
            device_xml.source(
                network=self.driver.network_name(interface.network))
            device_xml.target(dev="fuelnet{0}".format(interface.id))
            if interface.type is not None:
                device_xml.model(type=interface.model)

    def build_node_xml(self, node, emulator):
        """Generate node XML

        :type node: Node
        :type emulator: String
            :rtype : String
        """
        node_xml = XMLBuilder("domain", type=node.hypervisor)
        node_xml.name(
            self._get_name(node.environment and node.environment.name or '',
                           node.name))
        if self.driver.use_host_cpu:
            with node_xml.cpu(mode='host-model'):
                node_xml.model(fallback='forbid')
        node_xml.vcpu(str(node.vcpu))
        node_xml.memory(str(node.memory * 1024), unit='KiB')

        if self.driver.use_hugepages:
            with node_xml.memoryBacking:
                node_xml.hugepages

        node_xml.clock(offset='utc')
        with node_xml.clock.timer(name='rtc',
                                  tickpolicy='catchup', track='wall'):
            node_xml.catchup(
                threshold='123',
                slew='120',
                limit='10000')
        node_xml.clock.timer(
            name='pit',
            tickpolicy='delay')
        node_xml.clock.timer(
            name='hpet',
            present='yes' if self.driver.hpet else 'no')

        with node_xml.os:
            node_xml.type(node.os_type, arch=node.architecture)
            for boot_dev in json.loads(node.boot):
                node_xml.boot(dev=boot_dev)
            if self.driver.reboot_timeout:
                node_xml.bios(rebootTimeout='{0}'.format(
                    self.driver.reboot_timeout))
            if node.disk_devices.filter(bus='usb'):
                node_xml.bootmenu(enable='yes', timeout='3000')

        with node_xml.devices:
            node_xml.controller(type='usb', model='nec-xhci')
            node_xml.emulator(emulator)
            if node.has_vnc:
                if node.vnc_password:
                    node_xml.graphics(
                        type='vnc',
                        listen='0.0.0.0',
                        autoport='yes',
                        passwd=node.vnc_password)
                else:
                    node_xml.graphics(
                        type='vnc',
                        listen='0.0.0.0',
                        autoport='yes')

            for disk_device in node.disk_devices:
                self._build_disk_device(node_xml, disk_device)
            for interface in node.interfaces:
                self._build_interface_device(node_xml, interface)
            with node_xml.video:
                node_xml.model(type='vga', vram='9216', heads='1')
            with node_xml.serial(type='pty'):
                node_xml.target(port='0')
            with node_xml.console(type='pty'):
                node_xml.target(type='serial', port='0')
        return str(node_xml)

    def build_iface_bridge_xml(self, bridge_name, parent_name,
                               ip=None, prefix=None, vlanid=None):
        """Generate interface bridge XML

        :type bridge_name: String
        :type parent_name: String
        :type ip: IPAddress
        :type prefix: Integer
        :type vlanid: Integer
            :rtype : String
        """
        interface_xml = XMLBuilder('interface',
                                   type='bridge',
                                   name=bridge_name)
        interface_xml.start(mode="onboot")

        with interface_xml.bridge:
            if vlanid is not None:
                with interface_xml.interface(type="vlan",
                                             name="{0}.{1}".format(parent_name,
                                                                   vlanid)):
                    with interface_xml.vlan(tag=str(vlanid)):
                        interface_xml.start(mode="onboot")
                        interface_xml.interface(name=parent_name)
            else:
                interface_xml.interface(name=parent_name)

        if (ip is not None) and (prefix is not None):
            with interface_xml.protocol(family='ipv4'):
                interface_xml.ip(address=ip, prefix=prefix)
        return str(interface_xml)

    def build_iface_xml(self, name,
                        ip=None, prefix=None, vlanid=None):
        """Generate interface bridge XML

        :type name: String
        :type ip: IPAddress
        :type prefix: Integer
        :type vlanid: Integer
            :rtype : String
        """
        if vlanid is not None:
            iface_type = 'vlan'
            iface_name = "{0}.{1}".format(name, str(vlanid))
        else:
            iface_type = 'ethernet'
            iface_name = "{0}".format(name)

        interface_xml = XMLBuilder('interface',
                                   type=iface_type,
                                   name=iface_name)
        interface_xml.start(mode="onboot")

        if vlanid is not None:
            with interface_xml.vlan(tag=str(vlanid)):
                interface_xml.interface(name=name)

        if (ip is not None) and (prefix is not None):
            with interface_xml.protocol(family='ipv4'):
                interface_xml.ip(address=ip, prefix=prefix)
        return str(interface_xml)
