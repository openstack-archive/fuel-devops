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

import six

from devops.helpers import xmlgenerator


class LibvirtXMLBuilder(object):

    NAME_SIZE = 80

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
                          has_pxe_server=False, dhcp=False,
                          dhcp_range_start=None, dhcp_range_end=None,
                          tftp_root_dir=None):
        """Generate network XML

        :type network: Network
            :rtype : String
        """
        if addresses is None:
            addresses = []

        network_xml = xmlgenerator.XMLGenerator('network')
        network_xml.name(cls._crop_name(network_name))

        if forward == 'bridge':
            network_xml.bridge(
                name=bridge_name,
                delay='0')
        else:
            network_xml.bridge(
                name=bridge_name,
                stp='on' if stp else 'off',
                delay='0')

        if forward:
            network_xml.forward(mode=forward)

        if ip_network_address is None:
            return str(network_xml)

        if forward != 'bridge':
            with network_xml.ip(
                    address=ip_network_address,
                    prefix=ip_network_prefixlen):
                if has_pxe_server and tftp_root_dir:
                    network_xml.tftp(root=tftp_root_dir)
                if dhcp:
                    with network_xml.dhcp:
                        network_xml.range(
                            start=dhcp_range_start,
                            end=dhcp_range_end)
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
    def build_volume_xml(cls, name, capacity, vol_format, backing_store_path,
                         backing_store_format):
        """Generate volume XML

        :type volume: Volume
            :rtype : String
        """
        volume_xml = xmlgenerator.XMLGenerator('volume')
        volume_xml.name(cls._crop_name(name))
        volume_xml.capacity(str(capacity))
        with volume_xml.target:
            volume_xml.format(type=vol_format)
            volume_xml.permissions.mode("0644")
        if backing_store_path:
            with volume_xml.backingStore:
                volume_xml.path(backing_store_path)
                volume_xml.format(type=backing_store_format)
        return str(volume_xml)

    @classmethod
    def build_snapshot_xml(cls, name=None, description=None,
                           external=False, disk_only=False, memory_file='',
                           domain_isactive=False, local_disk_devices=None):
        """Generate snapshot XML

        :rtype : String
        :type name: String
        :type description: String
        """
        xml_builder = xmlgenerator.XMLGenerator('domainsnapshot')
        if name is not None:
            xml_builder.name(name)
        if description is not None:
            xml_builder.description(description)

        # EXTERNAL SNAPSHOT
        if external:
            # Add memory file for active machines
            if domain_isactive and not disk_only:
                xml_builder.memory(
                    file=memory_file,
                    snapshot='external')
            else:
                xml_builder.memory(snapshot='no')

            with xml_builder.disks:
                for disk in local_disk_devices or []:
                    with xml_builder.disk(name=disk['disk_target_dev'],
                                          snapshot='external'):
                        xml_builder.source(file=disk['disk_volume_path'])
        return str(xml_builder)

    @classmethod
    def _build_disk_device(cls, device_xml, disk_type, disk_device,
                           disk_volume_format, disk_volume_path, disk_bus,
                           disk_target_dev, disk_serial, disk_wwn):
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
            if disk_wwn:
                device_xml.wwn(disk_wwn)

    @classmethod
    def _build_interface_device(cls, device_xml, interface_type,
                                interface_mac_address, interface_network_name,
                                interface_target_dev, interface_model,
                                interface_filter):
        """Build xml for interface

        :param device_xml: XMLBuilder
        """

        with device_xml.interface(type=interface_type):
            device_xml.mac(address=interface_mac_address)
            device_xml.source(
                network=interface_network_name)
            if interface_target_dev is not None:
                # NOTE(astudenov): libvirt allows to create inteface devides
                # with the same name, but in this case
                # there will be an error when such nodes are started together
                device_xml.target(dev=interface_target_dev)
            if interface_model is not None:
                device_xml.model(type=interface_model)
            if interface_filter is not None:
                device_xml.filterref(filter=interface_filter)

    @classmethod
    def build_network_filter(cls, name, uuid=None, rule=None):
        """Generate nwfilter XML for network

        :type name: String
        :type uuid: String
        :type rule: dict
           :rtype : String
        """
        filter_xml = xmlgenerator.XMLGenerator('filter', name=name)
        if uuid:
            filter_xml.uuid(uuid)
        if rule:
            with filter_xml.rule(**rule):
                filter_xml.all()
        return str(filter_xml)

    @classmethod
    def build_interface_filter(cls, name, filterref, uuid=None, rule=None):
        """Generate nwfilter XML for interface

        :type name: String
        :type filterref: String
        :type uuid: String
        :type rule: dict
           :rtype : String
        """
        filter_xml = xmlgenerator.XMLGenerator('filter', name=name)
        filter_xml.filterref(filter=filterref)
        if uuid:
            filter_xml.uuid(uuid)
        if rule:
            with filter_xml.rule(**rule):
                filter_xml.all()
        return str(filter_xml)

    @classmethod
    def build_node_xml(cls, name, hypervisor, use_host_cpu, vcpu, memory,
                       use_hugepages, hpet, os_type, architecture, boot,
                       reboot_timeout, bootmenu_timeout, emulator,
                       has_vnc, vnc_password, local_disk_devices, interfaces,
                       acpi, numa):
        """Generate node XML

        :type node: Node
        :type emulator: String
            :rtype : String
        """
        node_xml = xmlgenerator.XMLGenerator("domain", type=hypervisor)
        node_xml.name(cls._crop_name(name))

        if acpi:
            with node_xml.features:
                # noinspection PyStatementEffect
                node_xml.acpi

        cpu_args = {}
        if use_host_cpu:
            cpu_args['mode'] = 'host-passthrough'
        if numa:
            with node_xml.cpu(**cpu_args):
                with node_xml.numa:
                    for cell in numa:
                        node_xml.cell(
                            cpus=str(cell['cpus']),
                            memory=str(cell['memory'] * 1024),
                            unit='KiB',
                        )
        elif cpu_args:
            node_xml.cpu(**cpu_args)
        node_xml.vcpu(str(vcpu))
        node_xml.memory(str(memory * 1024), unit='KiB')

        if use_hugepages:
            with node_xml.memoryBacking:
                # noinspection PyStatementEffect
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
            if bootmenu_timeout:
                node_xml.bootmenu(enable='yes', timeout=str(bootmenu_timeout))

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

            for disk_device in local_disk_devices:
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

        interface_xml = xmlgenerator.XMLGenerator(
            'interface',
            type=iface_type,
            name=iface_name)
        interface_xml.start(mode="onboot")

        if vlanid:
            with interface_xml.vlan(tag=str(vlanid)):
                interface_xml.interface(name=name)

        if (ip is not None) and (prefix is not None):
            with interface_xml.protocol(family='ipv4'):
                interface_xml.ip(address=ip, prefix=prefix)
        return str(interface_xml)
