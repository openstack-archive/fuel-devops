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

from xmlbuilder import XMLBuilder


class LibvirtXMLBuilder(object):

    NAME_SIZE = 80

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

    @classmethod
    def build_volume_xml(cls, name, capacity, format, backing_store_path,
                         backing_store_format):
        """Generate volume XML

        :type volume: Volume
            :rtype : String
        """
        volume_xml = XMLBuilder('volume')
        volume_xml.name(cls._crop_name(name))
        volume_xml.capacity(str(capacity))
        with volume_xml.target:
            volume_xml.format(type=format)
        if backing_store_path:
            with volume_xml.backingStore:
                volume_xml.path(backing_store_path)
                volume_xml.format(type=backing_store_format)
        return str(volume_xml)

    @classmethod
    def build_snapshot_xml(cls, name=None, description=None):
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

    @classmethod
    def _build_disk_device(cls, device_xml, disk_type, disk_device,
                           disk_volume_format, disk_volume_path, disk_bus,
                           disk_target_dev, disk_serial):
        """Build xml for disk

        :param device_xml: XMLBuilder
        :param disk_device: DiskDevice
        """

        with device_xml.disk(type=disk_type, device=disk_device):
            # https://bugs.launchpad.net/ubuntu/+source/qemu-kvm/+bug/741887
            device_xml.driver(type=disk_volume_format, cache="unsafe")
            device_xml.source(file=disk_volume_path)
            if disk_bus == 'usb':
                device_xml.target(
                    dev=disk_target_dev,
                    bus=disk_bus,
                    removable='on')
                device_xml.readonly()
            else:
                device_xml.target(
                    dev=disk_target_dev,
                    bus=disk_bus)
            device_xml.serial(disk_serial)

    @classmethod
    def _build_interface_device(cls, device_xml, interface_type,
                                interface_mac_address, interface_network_name,
                                interface_id, interface_model):
        """Build xml for interface

        :param device_xml: XMLBuilder
        :param interface: Network
        """

        with device_xml.interface(type=interface_type):
            device_xml.mac(address=interface_mac_address)
            device_xml.source(
                network=interface_network_name)
            device_xml.target(dev="fuelnet{0}".format(interface_id))
            if interface_type is not None:
                device_xml.model(type=interface_model)

    @classmethod
    def build_node_xml(cls, name, hypervisor, use_host_cpu, vcpu, memory,
                       use_hugepages, hpet, os_type, architecture, boot,
                       reboot_timeout, should_enable_boot_menu, emulator,
                       has_vnc, vnc_password, disk_devices, interfaces):
        """Generate node XML

        :type node: Node
        :type emulator: String
            :rtype : String
        """
        node_xml = XMLBuilder("domain", type=hypervisor)
        node_xml.name(cls._crop_name(name))
        if use_host_cpu:
            with node_xml.cpu(mode='host-model'):
                node_xml.model(fallback='forbid')
        node_xml.vcpu(str(vcpu))
        node_xml.memory(str(memory * 1024), unit='KiB')

        if use_hugepages:
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
            present='yes' if hpet else 'no')

        with node_xml.os:
            node_xml.type(os_type, arch=architecture)
            for boot_dev in boot:
                node_xml.boot(dev=boot_dev)
            if reboot_timeout:
                node_xml.bios(rebootTimeout=str(reboot_timeout))
            if should_enable_boot_menu:
                node_xml.bootmenu(enable='yes', timeout='3000')

        with node_xml.devices:
            node_xml.controller(type='usb', model='nec-xhci')
            node_xml.emulator(emulator)
            if has_vnc:
                if vnc_password:
                    node_xml.graphics(
                        type='vnc',
                        listen='0.0.0.0',
                        autoport='yes',
                        passwd=vnc_password)
                else:
                    node_xml.graphics(
                        type='vnc',
                        listen='0.0.0.0',
                        autoport='yes')

            for disk_device in disk_devices:
                cls._build_disk_device(node_xml, **disk_device)
            for interface in interfaces:
                cls._build_interface_device(node_xml, **interface)
            with node_xml.video:
                node_xml.model(type='vga', vram='9216', heads='1')
            with node_xml.serial(type='pty'):
                node_xml.target(port='0')
            with node_xml.console(type='pty'):
                node_xml.target(type='serial', port='0')
        return str(node_xml)
