#    Copyright 2013 - 2016 Mirantis, Inc.
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

from __future__ import unicode_literals

import hashlib
from sys import version_info
from xml.etree import ElementTree as ET

import six


class LibvirtXMLBuilder(object):

    NAME_SIZE = 80
    hdr = '<?xml version="1.0" encoding="utf-8" ?>'

    @classmethod
    def _crop_name(cls, name):
        if len(name) > cls.NAME_SIZE:
            if isinstance(name, six.string_types):
                hash_str = hashlib.md5(name.encode('utf8')).hexdigest()
            else:
                hash_str = hashlib.md5(name).hexdigest()
            name = (hash_str + name)[:cls.NAME_SIZE]
        return name

    @classmethod
    def build_network_xml(cls, network_name, bridge_name, addresses=None,
                          forward=None, ip_network_address=None,
                          ip_network_prefixlen=None, stp=True,
                          has_pxe_server=False, has_dhcp_server=False,
                          dhcp_range_start=None, dhcp_range_end=None,
                          tftp_root_dir=None):
        """Generate network XML

        :type network: Network
            :rtype : String
        """
        if addresses is None:
            addresses = []

        network_xml = ET.Element('network')
        ET.SubElement(network_xml, 'name').text = cls._crop_name(network_name)

        ET.SubElement(
            network_xml, 'bridge',
            {'name': bridge_name, 'stp': 'on' if stp else 'off', 'delay': '0'})

        if forward:
            ET.SubElement(network_xml, 'forward', {'mode': forward})

        if ip_network_address is None:
            result = cls.hdr + pretty_dump_xml(network_xml)
            if version_info.major == 2:
                return result.encode('utf8')
            return result

        ip = ET.SubElement(
            network_xml, 'ip',
            {'address': ip_network_address, 'prefix': ip_network_prefixlen})
        if has_pxe_server and tftp_root_dir:
            ET.SubElement(ip, 'tftp', {'root': tftp_root_dir})

        if has_dhcp_server:
            dhcp = ET.SubElement(ip, 'dhcp')
            ET.SubElement(
                dhcp, 'range', {
                    'start': dhcp_range_start,
                    'end': dhcp_range_end})
            for address in addresses:
                ET.SubElement(
                    dhcp, 'host', {
                        'mac': address['mac'],
                        'ip': address['ip'],
                        'name': address['name']})
            if has_pxe_server:
                ET.SubElement(dhcp, 'bootp', {'file': 'pxelinux.0'})

        result = cls.hdr + pretty_dump_xml(network_xml)
        if version_info.major == 2:
            return result.encode('utf8')
        return result

    @classmethod
    def build_volume_xml(cls, name, capacity, format, backing_store_path,
                         backing_store_format):
        """Generate volume XML

        :type volume: Volume
            :rtype : String
        """
        volume_xml = ET.Element('volume')
        ET.SubElement(volume_xml, 'name').text = cls._crop_name(name)
        ET.SubElement(volume_xml, 'capacity').text = str(capacity)
        target = ET.SubElement(volume_xml, 'target')
        ET.SubElement(target, 'format', {'type': format})
        ET.SubElement(
            ET.SubElement(target, 'permissions'),
            'mode').text = "0644"

        if backing_store_path:
            backing_store = ET.SubElement(volume_xml, 'backingStore')
            ET.SubElement(backing_store, 'path').text = backing_store_path
            ET.SubElement(
                backing_store, 'format', {'type': backing_store_format})
        result = cls.hdr + pretty_dump_xml(volume_xml)
        if version_info.major == 2:
            return result.encode('utf8')
        return result

    @classmethod
    def build_snapshot_xml(cls, name=None, description=None,
                           external=False, disk_only=False, memory_file='',
                           domain_isactive=False, local_disk_devices=None):
        """Generate snapshot XML

        :rtype : String
        :type name: String
        :type description: String
        """
        domainsnapshot_xml = ET.Element('domainsnapshot')
        if name is not None:
            ET.SubElement(domainsnapshot_xml, 'name').text = name
        if description is not None:
            ET.SubElement(domainsnapshot_xml, 'description').text = description

        # EXTERNAL SNAPSHOT
        if external:
            # Add memory file for active machines
            if domain_isactive and not disk_only:
                ET.SubElement(
                    domainsnapshot_xml, 'memory', {
                        'file': memory_file,
                        'snapshot': 'external'})
            else:
                ET.SubElement(
                    domainsnapshot_xml, 'memory', {'snapshot': 'no'})

            disks = ET.SubElement(domainsnapshot_xml, 'disks')

            for disk in local_disk_devices or []:
                ET.SubElement(
                    disks, 'disk', {
                        'name': disk['disk_target_dev'],
                        'file': disk['disk_volume_path'],
                        'snapshot': 'external'})
        result = cls.hdr + pretty_dump_xml(domainsnapshot_xml)
        if version_info.major == 2:
            return result.encode('utf8')
        return result

    @classmethod
    def _build_disk_device(cls, device_xml, disk_type, disk_device,
                           disk_volume_format, disk_volume_path, disk_bus,
                           disk_target_dev, disk_serial):
        """Build xml for disk

        :param device_xml: XMLBuilder
        :param disk_device: DiskDevice
        """

        disk = ET.SubElement(
            device_xml, 'disk', {
                'type': disk_type, 'device': disk_device})

        # https://bugs.launchpad.net/ubuntu/+source/qemu-kvm/+bug/741887
        ET.SubElement(
            disk, 'driver', {'type': disk_volume_format, 'cache': "unsafe"})

        ET.SubElement(disk, 'source', {'file': disk_volume_path})

        if disk_bus == 'usb':
            ET.SubElement(
                disk, 'target', {
                    'dev': disk_target_dev,
                    'bus': disk_bus,
                    'removable': 'on'})

            ET.SubElement(disk, 'readonly')
        else:
            ET.SubElement(
                disk, 'target', {
                    'dev': disk_target_dev,
                    'bus': disk_bus})

        ET.SubElement(disk, 'serial').text = disk_serial

    @classmethod
    def _build_interface_device(cls, device_xml, interface_type,
                                interface_mac_address, interface_network_name,
                                interface_id, interface_model):
        """Build xml for interface

        :param device_xml: XMLBuilder
        :param interface: Network
        """
        interface = ET.SubElement(
            device_xml, 'interface', {'type': interface_type})

        ET.SubElement(interface, 'mac', {'address': interface_mac_address})
        ET.SubElement(interface, 'source', {'network': interface_network_name})
        ET.SubElement(
            interface, 'target', {'dev': "virnet{0}".format(interface_id)})

        if interface_model is not None:
            ET.SubElement(interface, 'model', {'type': interface_model})

    @classmethod
    def build_node_xml(cls, name, hypervisor, use_host_cpu, vcpu, memory,
                       use_hugepages, hpet, os_type, architecture, boot,
                       reboot_timeout, bootmenu_timeout, emulator,
                       has_vnc, vnc_password, local_disk_devices, interfaces):
        """Generate node XML

        :type node: Node
        :type emulator: String
            :rtype : String
        """
        node_xml = ET.Element('domain', {'type': hypervisor})
        ET.SubElement(node_xml, 'name').text = cls._crop_name(name)
        if use_host_cpu:
            ET.SubElement(node_xml, 'cpu', {'mode': 'host-passthrough'})
        ET.SubElement(node_xml, 'vcpu').text = str(vcpu)
        ET.SubElement(
            node_xml, 'memory', {'unit': 'KiB'}).text = str(memory * 1024)

        if use_hugepages:
            ET.SubElement(
                ET.SubElement(node_xml, 'memoryBacking'),
                'hugepages')

        ET.SubElement(node_xml, 'clock', {'offset': 'utc'})

        ET.SubElement(
            ET.SubElement(
                ET.SubElement(node_xml, 'clock'),
                'timer', {
                    'name': 'rtc',
                    'tickpolicy': 'catchup',
                    'track': 'wall'}),
            'catchup', {
                'threshold': '123',
                'slew': '120',
                'limit': '10000'}
        )

        ET.SubElement(
            ET.SubElement(node_xml, 'clock'),
            'timer', {
                'name': 'pit',
                'tickpolicy': 'delay'})

        ET.SubElement(
            ET.SubElement(node_xml, 'clock'),
            'timer', {
                'name': 'hpet',
                'present': 'yes' if hpet else 'no'})

        os = ET.SubElement(node_xml, 'os')
        ET.SubElement(os, 'type', {'arch': architecture}).text = 'hvm'
        for boot_dev in boot:
            ET.SubElement(os, 'boot', {'dev': boot_dev})

        if reboot_timeout:
            ET.SubElement(os, 'bios', {'rebootTimeout': str(reboot_timeout)})

        if bootmenu_timeout:
            ET.SubElement(
                os, 'bootmenu', {
                    'enable': 'yes',
                    'timeout': str(bootmenu_timeout)})

        devices = ET.SubElement(node_xml, 'devices')
        ET.SubElement(
            devices, 'controller', {'type': 'usb', 'model': 'nec-xhci'})
        ET.SubElement(
            devices, 'emulator').text = emulator

        if has_vnc:
            if vnc_password:
                ET.SubElement(
                    devices, 'graphics', {
                        'type': 'vnc',
                        'listen': '0.0.0.0',
                        'autoport': 'yes',
                        'passwd': vnc_password})
            else:
                ET.SubElement(
                    devices, 'graphics', {
                        'type': 'vnc',
                        'listen': '0.0.0.0',
                        'autoport': 'yes'})

            for disk_device in local_disk_devices:
                cls._build_disk_device(devices, **disk_device)
            for interface in interfaces:
                cls._build_interface_device(devices, **interface)

            ET.SubElement(
                ET.SubElement(devices, 'video'),
                'model', {'type': 'vga', 'vram': '9216', 'heads': '1'})
            ET.SubElement(
                ET.SubElement(devices, 'serial', {'type': 'pty'}),
                'target', {'port': '0'})
            ET.SubElement(
                ET.SubElement(devices, 'console', {'type': 'pty'}),
                'target', {'type': 'serial', 'port': '0'})
        result = cls.hdr + pretty_dump_xml(node_xml)
        if version_info.major == 2:
            return result.encode('utf8')
        return result

    @classmethod
    def build_iface_xml(cls, name, ip=None, prefix=None, vlanid=None):
        """Generate interface bridge XML

        :type name: String
        :type ip: IPAddress
        :type prefix: Integer
        :type vlanid: Integer
            :rtype : String
        """
        if vlanid:
            iface_type = 'vlan'
            iface_name = "{0}.{1}".format(name, str(vlanid))
        else:
            iface_type = 'ethernet'
            iface_name = "{0}".format(name)

        interface_xml = ET.Element(
            'interface', {'type': iface_type, 'name': iface_name})
        ET.SubElement(interface_xml, 'start', {'mode': "onboot"})

        if vlanid:
            ET.SubElement(
                ET.SubElement(interface_xml, 'vlan', {'tag': str(vlanid)}),
                'interface', {'name': name})

        if (ip is not None) and (prefix is not None):
            ET.SubElement(
                ET.SubElement(interface_xml, 'protocol', {'family': 'ipv4'}),
                'ip', {'address': ip, 'prefix': prefix})

        result = cls.hdr + pretty_dump_xml(interface_xml)
        if version_info.major == 2:
            return result.encode('utf8')
        return result


def pretty_dump_xml(src):
    result = ''
    indent = 1
    tags = ET.tostring(src).decode('utf-8').replace('><', '>|<').split('|')
    for tag in tags:
        indent_diff = 0
        if tag.startswith('</'):
            indent -= 4
        elif tag.count('</') == 0 and not tag.endswith('/>'):
            indent_diff += 4
        result += "{nl:{indent}}{item}".format(
            nl='\n',
            indent=indent,
            item=tag)
        indent += indent_diff
    return result
