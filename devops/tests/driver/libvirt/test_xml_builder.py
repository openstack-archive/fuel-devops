#    Copyright 2016 Mirantis, Inc.
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

from unittest import TestCase

from netaddr import IPNetwork

from devops.driver.libvirt.libvirt_xml_builder import LibvirtXMLBuilder


class BaseTestXMLBuilder(TestCase):

    def setUp(self):
        self.xml_builder = LibvirtXMLBuilder


class TestCrop(BaseTestXMLBuilder):

    def test_crop_name(self):
        big_name = (
            'very_very_very_very_very_very_very_very_very_very_very_'
            'very_very_very_very_very_very_very_very_very_very_very_'
            'very_very_very_very_very_very_very_very_very_big_name')
        small_name = self.xml_builder._crop_name(big_name)
        assert len(small_name) == self.xml_builder.NAME_SIZE
        assert small_name == (
            'ca53efbcf06da1b3f119c4ce6b575acavery_very_very_very_'
            'very_very_very_very_very_ver')


class TestNetworkXml(BaseTestXMLBuilder):

    def setUp(self):
        super(TestNetworkXml, self).setUp()

        self.address = [
            {
                'mac': '64:65:f3:5c:a5:a2',
                'ip': '172.0.1.61',
                'name': 'test_admin',
            },
            {
                'mac': '64:70:8d:b0:4c:ad',
                'ip': '172.0.1.62',
                'name': 'test_public',
            },
        ]

        self.ip_net = IPNetwork('172.0.1.1/24')
        self.ip_network_address = '172.0.1.1'
        self.ip_network_prefixlen = '24'
        self.dhcp_range_start = '172.0.1.2'
        self.dhcp_range_end = '172.0.1.254'

    def test_default(self):
        xml = self.xml_builder.build_network_xml(
            network_name='test_name',
            bridge_name='virbr13',
        )

        assert xml == ('<?xml version="1.0" encoding="utf-8"?>\n'
                       '<network>\n'
                       '    <name>test_name</name>\n'
                       '    <bridge delay="0" name="virbr13" stp="on"/>\n'
                       '</network>\n')

    def test_stp_off(self):
        xml = self.xml_builder.build_network_xml(
            network_name='test_name',
            bridge_name='virbr13',
            stp=False,
        )
        assert xml == ('<?xml version="1.0" encoding="utf-8"?>\n'
                       '<network>\n'
                       '    <name>test_name</name>\n'
                       '    <bridge delay="0" name="virbr13" stp="off"/>\n'
                       '</network>\n')

    def test_ip_network_bridge(self):
        xml = self.xml_builder.build_network_xml(
            network_name='test_name',
            bridge_name='virbr13',
            forward='bridge',
        )
        assert xml == ('<?xml version="1.0" encoding="utf-8"?>\n'
                       '<network>\n'
                       '    <name>test_name</name>\n'
                       '    <bridge delay="0" name="virbr13" stp="on"/>\n'
                       '    <forward mode="bridge"/>\n'
                       '</network>\n')

    def test_ip_network_nat(self):
        xml = self.xml_builder.build_network_xml(
            network_name='test_name',
            bridge_name='virbr13',
            forward='nat',
            ip_network_address=self.ip_network_address,
            ip_network_prefixlen=self.ip_network_prefixlen,
        )
        assert xml == ('<?xml version="1.0" encoding="utf-8"?>\n'
                       '<network>\n'
                       '    <name>test_name</name>\n'
                       '    <bridge delay="0" name="virbr13" stp="on"/>\n'
                       '    <forward mode="nat"/>\n'
                       '    <ip address="172.0.1.1" prefix="24"/>\n'
                       '</network>\n')

    def test_ip_network_route(self):
        xml = self.xml_builder.build_network_xml(
            network_name='test_name',
            bridge_name='virbr13',
            forward='route',
            ip_network_address=self.ip_network_address,
            ip_network_prefixlen=self.ip_network_prefixlen,
        )
        assert xml == ('<?xml version="1.0" encoding="utf-8"?>\n'
                       '<network>\n'
                       '    <name>test_name</name>\n'
                       '    <bridge delay="0" name="virbr13" stp="on"/>\n'
                       '    <forward mode="route"/>\n'
                       '    <ip address="172.0.1.1" prefix="24"/>\n'
                       '</network>\n')

    def test_pxe_server(self):
        xml = self.xml_builder.build_network_xml(
            network_name='test_name',
            bridge_name='virbr13',
            forward='nat',
            ip_network_address=self.ip_network_address,
            ip_network_prefixlen=self.ip_network_prefixlen,
            has_pxe_server=True,
            tftp_root_dir='/tmp',
        )
        assert xml == ('<?xml version="1.0" encoding="utf-8"?>\n'
                       '<network>\n'
                       '    <name>test_name</name>\n'
                       '    <bridge delay="0" name="virbr13" stp="on"/>\n'
                       '    <forward mode="nat"/>\n'
                       '    <ip address="172.0.1.1" prefix="24">\n'
                       '        <tftp root="/tmp"/>\n'
                       '    </ip>\n'
                       '</network>\n')

    def test_dhcp_server(self):
        xml = self.xml_builder.build_network_xml(
            network_name='test_name',
            bridge_name='virbr13',
            forward='nat',
            addresses=self.address,
            ip_network_address=self.ip_network_address,
            ip_network_prefixlen=self.ip_network_prefixlen,
            has_dhcp_server=True,
            dhcp_range_start=self.dhcp_range_start,
            dhcp_range_end=self.dhcp_range_end,
        )
        assert xml == """<?xml version="1.0" encoding="utf-8"?>
<network>
    <name>test_name</name>
    <bridge delay="0" name="virbr13" stp="on"/>
    <forward mode="nat"/>
    <ip address="172.0.1.1" prefix="24">
        <dhcp>
            <range end="172.0.1.254" start="172.0.1.2"/>
            <host ip="172.0.1.61" mac="64:65:f3:5c:a5:a2" name="test_admin"/>
            <host ip="172.0.1.62" mac="64:70:8d:b0:4c:ad" name="test_public"/>
        </dhcp>
    </ip>
</network>
"""

    def test_dhcp_server_plus_pxe(self):
        xml = self.xml_builder.build_network_xml(
            network_name='test_name',
            bridge_name='virbr13',
            forward='nat',
            addresses=self.address,
            ip_network_address=self.ip_network_address,
            ip_network_prefixlen=self.ip_network_prefixlen,
            has_dhcp_server=True,
            dhcp_range_start=self.dhcp_range_start,
            dhcp_range_end=self.dhcp_range_end,
            has_pxe_server=True,
            tftp_root_dir='/tmp',
        )
        assert xml == """<?xml version="1.0" encoding="utf-8"?>
<network>
    <name>test_name</name>
    <bridge delay="0" name="virbr13" stp="on"/>
    <forward mode="nat"/>
    <ip address="172.0.1.1" prefix="24">
        <tftp root="/tmp"/>
        <dhcp>
            <range end="172.0.1.254" start="172.0.1.2"/>
            <host ip="172.0.1.61" mac="64:65:f3:5c:a5:a2" name="test_admin"/>
            <host ip="172.0.1.62" mac="64:70:8d:b0:4c:ad" name="test_public"/>
            <bootp file="pxelinux.0"/>
        </dhcp>
    </ip>
</network>
"""


class TestVolumeXml(BaseTestXMLBuilder):

    def test_default(self):
        xml = self.xml_builder.build_volume_xml(
            name='test_name',
            capacity=1048576,
            format='qcow2',
            backing_store_path=None,
            backing_store_format=None,
        )
        assert xml == ('<?xml version="1.0" encoding="utf-8"?>\n'
                       '<volume>\n'
                       '    <name>test_name</name>\n'
                       '    <capacity>1048576</capacity>\n'
                       '    <target>\n'
                       '        <format type="qcow2"/>\n'
                       '        <permissions>\n'
                       '            <mode>0644</mode>\n'
                       '        </permissions>\n'
                       '    </target>\n'
                       '</volume>\n')

    def test_format(self):
        xml = self.xml_builder.build_volume_xml(
            name='test_name',
            capacity=1048576,
            format='raw',
            backing_store_path=None,
            backing_store_format=None,
        )
        assert xml == ('<?xml version="1.0" encoding="utf-8"?>\n'
                       '<volume>\n'
                       '    <name>test_name</name>\n'
                       '    <capacity>1048576</capacity>\n'
                       '    <target>\n'
                       '        <format type="raw"/>\n'
                       '        <permissions>\n'
                       '            <mode>0644</mode>\n'
                       '        </permissions>\n'
                       '    </target>\n'
                       '</volume>\n')

    def test_backing_store(self):
        xml = self.xml_builder.build_volume_xml(
            name='test_name',
            capacity=1048576,
            format='qcow2',
            backing_store_path='/tmp/master.img',
            backing_store_format='raw',
        )
        assert xml == ('<?xml version="1.0" encoding="utf-8"?>\n'
                       '<volume>\n'
                       '    <name>test_name</name>\n'
                       '    <capacity>1048576</capacity>\n'
                       '    <target>\n'
                       '        <format type="qcow2"/>\n'
                       '        <permissions>\n'
                       '            <mode>0644</mode>\n'
                       '        </permissions>\n'
                       '    </target>\n'
                       '    <backingStore>\n'
                       '        <path>/tmp/master.img</path>\n'
                       '        <format type="raw"/>\n'
                       '    </backingStore>\n'
                       '</volume>\n')


class TestSnapshotXml(BaseTestXMLBuilder):

    def test_default(self):
        xml = self.xml_builder.build_snapshot_xml()
        assert xml == ('<?xml version="1.0" encoding="utf-8"?>\n'
                       '<domainsnapshot/>\n')

    def test_name(self):
        xml = self.xml_builder.build_snapshot_xml(
            name='test_name',
        )
        assert xml == ('<?xml version="1.0" encoding="utf-8"?>\n'
                       '<domainsnapshot>\n'
                       '    <name>test_name</name>\n'
                       '</domainsnapshot>\n')

    def test_description(self):
        xml = self.xml_builder.build_snapshot_xml(
            description='test_description',
        )
        assert xml == ('<?xml version="1.0" encoding="utf-8"?>\n'
                       '<domainsnapshot>\n'
                       '    <description>test_description</description>\n'
                       '</domainsnapshot>\n')

    def test_name_description(self):
        xml = self.xml_builder.build_snapshot_xml(
            name='test_name',
            description='test_description',
        )
        assert xml == ('<?xml version="1.0" encoding="utf-8"?>\n'
                       '<domainsnapshot>\n'
                       '    <name>test_name</name>\n'
                       '    <description>test_description</description>\n'
                       '</domainsnapshot>\n')


class TestNodeXml(BaseTestXMLBuilder):

    def setUp(self):
        super(TestNodeXml, self).setUp()

        self.disk_devices = [
            dict(
                disk_type='file',
                disk_device='disk',
                disk_volume_format='raw',
                disk_volume_path='/tmp/volume.img',
                disk_bus='usb',
                disk_target_dev='sda',
                disk_serial='ca9dcfe5a48540f39537eb3cbd96f370',
                disk_wwn=None,
            ),
            dict(
                disk_type='file',
                disk_device='cdrom',
                disk_volume_format='qcow2',
                disk_volume_path='/tmp/volume2.img',
                disk_bus='ide',
                disk_target_dev='sdb',
                disk_serial='8c81c0e0aba448fabcb54c34f61d8d07',
                disk_wwn='013fb0aefb9e64ee',
            ),
        ]

        self.interfaces = [
            dict(
                interface_type='network',
                interface_mac_address='64:70:74:90:bc:84',
                interface_network_name='test_admin',
                interface_id=132,
                interface_model='e1000',
            ),
            dict(
                interface_type='network',
                interface_mac_address='64:de:6c:44:de:46',
                interface_network_name='test_public',
                interface_id=133,
                interface_model='pcnet',
            ),
        ]

    def test_default(self):
        xml = self.xml_builder.build_node_xml(
            name='test_name',
            hypervisor='test_description',
            use_host_cpu=False,
            vcpu=1,
            memory=1024,
            use_hugepages=False,
            hpet=True,
            os_type='hvm',
            architecture='x86_64',
            boot=['network', 'cdrom', 'hd'],
            reboot_timeout=10,
            bootmenu_timeout=0,
            emulator='/usr/lib64/xen/bin/qemu-dm',
            has_vnc=True,
            vnc_password='123456',
            local_disk_devices=[],
            interfaces=[],
        )

        assert xml == """<?xml version="1.0" encoding="utf-8"?>
<domain type="test_description">
    <name>test_name</name>
    <vcpu>1</vcpu>
    <memory unit="KiB">1048576</memory>
    <clock offset="utc"/>
    <clock>
        <timer name="rtc" tickpolicy="catchup" track="wall">
            <catchup limit="10000" slew="120" threshold="123"/>
        </timer>
    </clock>
    <clock>
        <timer name="pit" tickpolicy="delay"/>
    </clock>
    <clock>
        <timer name="hpet" present="yes"/>
    </clock>
    <os>
        <type arch="x86_64">hvm</type>
        <boot dev="network"/>
        <boot dev="cdrom"/>
        <boot dev="hd"/>
        <bios rebootTimeout="10"/>
    </os>
    <devices>
        <controller model="nec-xhci" type="usb"/>
        <emulator>/usr/lib64/xen/bin/qemu-dm</emulator>
        <graphics autoport="yes" listen="0.0.0.0" passwd="123456" type="vnc"/>
        <video>
            <model heads="1" type="vga" vram="9216"/>
        </video>
        <serial type="pty">
            <target port="0"/>
        </serial>
        <console type="pty">
            <target port="0" type="serial"/>
        </console>
    </devices>
</domain>
"""

    def test_with_devices(self):
        xml = self.xml_builder.build_node_xml(
            name='test_name',
            hypervisor='test_description',
            use_host_cpu=True,
            vcpu=4,
            memory=1024,
            use_hugepages=True,
            hpet=False,
            os_type='hvm',
            architecture='i686',
            boot=['cdrom', 'hd'],
            reboot_timeout=10,
            bootmenu_timeout=3000,
            emulator='/usr/lib64/xen/bin/qemu-dm',
            has_vnc=True,
            vnc_password=None,
            local_disk_devices=self.disk_devices,
            interfaces=self.interfaces,
        )

        assert xml == """<?xml version="1.0" encoding="utf-8"?>
<domain type="test_description">
    <name>test_name</name>
    <cpu mode="host-passthrough"/>
    <vcpu>4</vcpu>
    <memory unit="KiB">1048576</memory>
    <memoryBacking>
        <hugepages/>
    </memoryBacking>
    <clock offset="utc"/>
    <clock>
        <timer name="rtc" tickpolicy="catchup" track="wall">
            <catchup limit="10000" slew="120" threshold="123"/>
        </timer>
    </clock>
    <clock>
        <timer name="pit" tickpolicy="delay"/>
    </clock>
    <clock>
        <timer name="hpet" present="no"/>
    </clock>
    <os>
        <type arch="i686">hvm</type>
        <boot dev="cdrom"/>
        <boot dev="hd"/>
        <bios rebootTimeout="10"/>
        <bootmenu enable="yes" timeout="3000"/>
    </os>
    <devices>
        <controller model="nec-xhci" type="usb"/>
        <emulator>/usr/lib64/xen/bin/qemu-dm</emulator>
        <graphics autoport="yes" listen="0.0.0.0" type="vnc"/>
        <disk device="disk" type="file">
            <driver cache="unsafe" type="raw"/>
            <source file="/tmp/volume.img"/>
            <target bus="usb" dev="sda" removable="on"/>
            <readonly/>
            <serial>ca9dcfe5a48540f39537eb3cbd96f370</serial>
        </disk>
        <disk device="cdrom" type="file">
            <driver cache="unsafe" type="qcow2"/>
            <source file="/tmp/volume2.img"/>
            <target bus="ide" dev="sdb"/>
            <serial>8c81c0e0aba448fabcb54c34f61d8d07</serial>
            <wwn>013fb0aefb9e64ee</wwn>
        </disk>
        <interface type="network">
            <mac address="64:70:74:90:bc:84"/>
            <source network="test_admin"/>
            <target dev="virnet132"/>
            <model type="e1000"/>
        </interface>
        <interface type="network">
            <mac address="64:de:6c:44:de:46"/>
            <source network="test_public"/>
            <target dev="virnet133"/>
            <model type="pcnet"/>
        </interface>
        <video>
            <model heads="1" type="vga" vram="9216"/>
        </video>
        <serial type="pty">
            <target port="0"/>
        </serial>
        <console type="pty">
            <target port="0" type="serial"/>
        </console>
    </devices>
</domain>
"""
