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

from xmlbuilder import XMLBuilder

# from devops.error import DevopsError


class LibvirtXMLBuilder(object):

    NAME_SIZE = 80

    @classmethod
    def _get_name(cls, *args):
        name = '_'.join(filter(None, list(args)))
        return cls._crop_name(name)

    @classmethod
    def _crop_name(cls, name):
        if len(name) > cls.NAME_SIZE:
            hash_str = str(hash(name))
            name = hash_str + name[len(name) - cls.NAME_SIZE + len(hash_str):]
        return name

    @classmethod
    def build_network_xml(cls, network_name, bridge_id, addresses,
                          forward='nat', ip_network=None, stp=True,
                          has_pxe_server=False, has_dhcp_server=False,
                          tftp_root_dir=None):
        """Generate network XML

        :type network: Network
            :rtype : String
        """
        network_xml = XMLBuilder('network')
        network_xml.name(cls._crop_name(network_name))

        network_xml.bridge(
            name='fuelbr{0}'.format(bridge_id),
            stp='on' if stp else 'off',
            delay='0')

        network_xml.forward(mode=forward)

        if ip_network is None:
            return str(network_xml)

        with network_xml.ip(
                address=str(ip_network[1]),
                prefix=str(ip_network.prefixlen)):
            if has_pxe_server:
                network_xml.tftp(root=tftp_root_dir)
            if has_dhcp_server:
                with network_xml.dhcp:
                    network_xml.range(
                        start=str(ip_network.ip_start),
                        end=str(ip_network.ip_end))
                    for address in addresses:
                        network_xml.host(
                            mac=address['mac'],
                            ip=address['ip'],
                            name=address['name'],
                        )
                    if has_pxe_server:
                        network_xml.bootp(file='pxelinux.0')

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
            if node.should_enable_boot_menu:
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
