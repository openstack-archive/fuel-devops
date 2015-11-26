#    Copyright 2014 Mirantis, Inc.
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
import random
from unittest import TestCase

from lxml import etree
import mock

from devops.driver.libvirt.libvirt_xml_builder import LibvirtXMLBuilder
from devops.tests import factories


class BaseTestXMLBuilder(TestCase):

    def setUp(self):
        # TODO(prmtl): make it fuzzy
        self.volume_path = "volume_path_mock"
        self.xml_builder = LibvirtXMLBuilder(mock.Mock())
        self.xml_builder.driver.volume_path = mock.Mock(
            return_value=self.volume_path
        )
        self.xml_builder.driver.network_name = mock.Mock(
            return_value="network_name_mock"
        )
        self.xml_builder.driver.reboot_timeout = None
        self.net = mock.Mock()
        self.node = mock.Mock()
        self.xml_builder.driver.use_hugepages = None

    def _reformat_xml(self, xml):
        """Takes XML in string, parses it and returns pretty printed XML."""
        return etree.tostring(etree.fromstring(xml), pretty_print=True)

    def assertXMLEqual(self, first, second):
        """Compare if two XMLs are equal.

        It parses provided XMLs and converts back to string to minimise
        errors caused by whitespaces.
        """
        first = self._reformat_xml(first)
        second = self._reformat_xml(second)
        # NOTE(prmtl): this assert provide better reporting (diff) in py.test
        assert first == second

    def assertXMLIn(self, member, container):
        """Checks if one XML is included in another XML, dummy way.

        If check fail, it pretty prints both elements
        """
        member = self._reformat_xml(member)
        container = self._reformat_xml(container)

        if member not in container:
            msg = "\n{0}\n\nnot found in\n\n{1}".format(member, container)
            self.fail(msg)

    def assertXMLNotIn(self, member, container):
        """Checks if one XML is not included in another XML, dummy way.

        If check fail, it pretty prints both elements
        """
        member = self._reformat_xml(member)
        container = self._reformat_xml(container)

        if member in container:
            msg = "\n{0}\n\nunexpectedly found in\n\n{1}".format(member,
                                                                 container)
            self.fail(msg)

    def assertXpath(self, xpath, xml):
        """Asserts XPath is valid for given XML."""
        xml = etree.fromstring(xml)
        if not xml.xpath(xpath):
            self.fail('No result for XPath on element\n'
                      'XPath: {xpath}\n'
                      'Element:\n'
                      '{xml}'.format(
                          xpath=xpath,
                          xml=etree.tostring(xml, pretty_print=True)))


class TestNetworkXml(BaseTestXMLBuilder):

    def setUp(self):
        super(TestNetworkXml, self).setUp()
        self.net.name = 'test_name'
        self.net.environment.name = 'test_env_name'
        self.net.id = random.randint(1, 100)
        self.net.forward = None
        self.net.ip_network = None
        self.net.has_dhcp_server = False

    def test_net_name_bridge_name(self):
        bridge_name = 'fuelbr{0}'.format(self.net.id)
        xml = self.xml_builder.build_network_xml(self.net)
        self.assertXMLIn(
            '<name>{0}_{1}</name>'
            ''.format(self.net.environment.name, self.net.name),
            xml)
        self.assertXMLIn(
            '<bridge delay="0" name="{0}" stp="on" />'
            ''.format(bridge_name), xml)

    def test_forward(self):
        self.net.forward = "nat"
        xml = self.xml_builder.build_network_xml(self.net)
        self.assertXMLIn(
            '<forward mode="{0}" />'
            ''.format(self.net.forward), xml)

    def test_ip_network(self):
        ip = '172.0.1.1'
        prefix = '24'
        self.net.ip_network = "{0}/{1}".format(ip, prefix)
        self.net.has_pxe_server = False
        self.net.tftp_root_dir = '/tmp'
        xml = self.xml_builder.build_network_xml(self.net)
        string = '<ip address="{0}" prefix="{1}" />'.format(ip, prefix)
        self.assertXMLIn(string, xml)


class TestVolumeXml(BaseTestXMLBuilder):

    def setUp(self):
        super(TestVolumeXml, self).setUp()

    def get_xml(self, volume):
        """Generate XML from volume"""
        return self.xml_builder.build_volume_xml(volume)

    def test_full_volume_xml(self):
        volume = factories.VolumeFactory()
        expected = '''<?xml version="1.0" encoding="utf-8" ?>
<volume>
    <name>{env_name}_{name}</name>
    <capacity>{capacity}</capacity>
    <target>
        <format type="{format}" />
    </target>
    <backingStore>
        <path>{path}</path>
        <format type="{store_format}" />
    </backingStore>
</volume>'''.format(
            env_name=volume.environment.name,
            name=volume.name,
            capacity=volume.capacity,
            format=volume.format,
            path=self.volume_path,
            store_format=volume.backing_store.format,
        )
        xml = self.get_xml(volume)
        self.assertXMLEqual(expected, xml)
        self.xml_builder.driver.volume_path.assert_called_with(
            volume.backing_store)

    def test_name_without_env(self):
        volume = factories.VolumeFactory(environment=None)
        xml = self.get_xml(volume)
        self.assertXMLIn('<name>{0}</name>'.format(volume.name), xml)

    def test_no_backing_store(self):
        volume = factories.VolumeFactory(backing_store=None)
        xml = self.get_xml(volume)
        self.assertXpath("not(//backingStore)", xml)

    def test_backing_store(self):
        store_format = "raw"
        volume = factories.VolumeFactory(backing_store__format=store_format)
        xml = self.get_xml(volume)
        self.assertXMLIn('''
    <backingStore>
        <path>{path}</path>
        <format type="{format}" />
    </backingStore>'''.format(path=self.volume_path, format=store_format), xml)


class TestSnapshotXml(BaseTestXMLBuilder):

    def check_snaphot_xml(self, name, description, expected):
        result = self.xml_builder.build_snapshot_xml(name, description)
        self.assertXMLIn(expected, result)

    def test_no_name(self):
        name = None
        description = factories.fuzzy_string('test_description_')
        expected = '''
<domainsnapshot>
    <description>{0}</description>
</domainsnapshot>'''.format(description)
        self.check_snaphot_xml(name, description, expected)

    def test_no_description(self):
        name = factories.fuzzy_string('test_snapshot_')
        description = None
        expected = '''
<domainsnapshot>
    <name>{0}</name>
</domainsnapshot>'''.format(name)
        self.check_snaphot_xml(name, description, expected)

    def test_nothing_there(self):
        name = None
        description = None
        expected = '<domainsnapshot />'
        self.check_snaphot_xml(name, description, expected)

    def test_snapshot(self):
        name = factories.fuzzy_string('test_snapshot_')
        description = factories.fuzzy_string('test_description_')
        expected = '''
<domainsnapshot>
    <name>{0}</name>
    <description>{1}</description>
</domainsnapshot>'''.format(name, description)
        self.check_snaphot_xml(name, description, expected)


class TestNodeXml(BaseTestXMLBuilder):

    def setUp(self):
        super(TestNodeXml, self).setUp()

        self.node.hypervisor = 'test_hypervisor'
        self.node.name = 'test_name'
        self.node.environment.name = 'test_env_name'
        self.node.vcpu = random.randint(1, 10)
        self.node.memory = random.randint(128, 1024)
        self.node.os_type = 'test_os_type'
        self.node.architecture = 'test_architecture'
        self.node.boot = '["dev1", "dev2"]'
        self.node.has_vnc = None
        self.node.should_enable_boot_menu = False
        disk_devices = mock.MagicMock()
        disk_devices.filter.return_value = []
        self.node.disk_devices = disk_devices
        self.node.interfaces = []

    def test_node(self):
        xml = self.xml_builder.build_node_xml(self.node, 'test_emulator')
        boot = json.loads(self.node.boot)
        expected = '''
<domain type="test_hypervisor">
    <name>test_env_name_test_name</name>
    <cpu mode="host-passthrough" />
    <vcpu>{0}</vcpu>
    <memory unit="KiB">{1}</memory>
    <clock offset="utc" />
    <clock>
        <timer name="rtc" tickpolicy="catchup" track="wall">
            <catchup limit="10000" slew="120" threshold="123" />
        </timer>
    </clock>
    <clock>
        <timer name="pit" tickpolicy="delay" />
    </clock>
    <clock>
        <timer name="hpet" present="yes" />
    </clock>
    <os>
        <type arch="{2}">{3}</type>
        <boot dev="{4}" />
        <boot dev="{5}" />
    </os>
    <devices>
        <controller model="nec-xhci" type="usb" />
        <emulator>test_emulator</emulator>
        <video>
            <model heads="1" type="vga" vram="9216" />
        </video>
        <serial type="pty">
            <target port="0" />
        </serial>
        <console type="pty">
            <target port="0" type="serial" />
        </console>
    </devices>
</domain>'''.format(self.node.vcpu, str(self.node.memory * 1024),
                    self.node.architecture, self.node.os_type,
                    boot[0], boot[1])
        self.assertXMLIn(expected, xml)

    @mock.patch('devops.driver.libvirt.libvirt_xml_builder.uuid')
    def test_node_devices(self, mock_uuid):
        mock_uuid.uuid4.return_value.hex = 'disk-serial'
        volumes = [mock.Mock(uuid=i, format='frmt{0}'.format(i))
                   for i in range(3)]

        disk_devices = [
            mock.Mock(
                type='type{0}'.format(i),
                device='device{0}'.format(i),
                volume=volumes[i],
                target_dev='tdev{0}'.format(i),
                bus='bus{0}'.format(i)
            ) for i in range(3)
        ]
        self.node.disk_devices = mock.MagicMock()
        self.node.disk_devices.__iter__.return_value = iter(disk_devices)
        xml = self.xml_builder.build_node_xml(self.node, 'test_emulator')
        expected = '''
    <devices>
        <controller model="nec-xhci" type="usb" />
        <emulator>test_emulator</emulator>
        <disk device="device0" type="type0">
            <driver cache="unsafe" type="frmt0" />
            <source file="volume_path_mock" />
            <target bus="bus0" dev="tdev0" />
            <serial>disk-serial</serial>
        </disk>
        <disk device="device1" type="type1">
            <driver cache="unsafe" type="frmt1" />
            <source file="volume_path_mock" />
            <target bus="bus1" dev="tdev1" />
            <serial>disk-serial</serial>
        </disk>
        <disk device="device2" type="type2">
            <driver cache="unsafe" type="frmt2" />
            <source file="volume_path_mock" />
            <target bus="bus2" dev="tdev2" />
            <serial>disk-serial</serial>
        </disk>
        <video>
            <model heads="1" type="vga" vram="9216" />
        </video>
        <serial type="pty">
            <target port="0" />
        </serial>
        <console type="pty">
            <target port="0" type="serial" />
        </console>
    </devices>'''
        self.assertXMLIn(expected, xml)

    def test_node_interfaces(self):
        networks = [mock.Mock(uuid=i) for i in range(3)]
        self.node.interfaces = [
            mock.Mock(type='network'.format(i), mac_address='mac{0}'.format(i),
                      network=networks[i], id='id{0}'.format(i),
                      model='model{0}'.format(i)) for i in range(3)]
        xml = self.xml_builder.build_node_xml(self.node, 'test_emulator')
        self.assertXMLIn('''
    <devices>
        <controller model="nec-xhci" type="usb" />
        <emulator>test_emulator</emulator>
        <interface type="network">
            <mac address="mac0" />
            <source network="network_name_mock" />
            <target dev="fuelnetid0" />
            <model type="model0" />
        </interface>
        <interface type="network">
            <mac address="mac1" />
            <source network="network_name_mock" />
            <target dev="fuelnetid1" />
            <model type="model1" />
        </interface>
        <interface type="network">
            <mac address="mac2" />
            <source network="network_name_mock" />
            <target dev="fuelnetid2" />
            <model type="model2" />
        </interface>
        <video>
            <model heads="1" type="vga" vram="9216" />
        </video>
        <serial type="pty">
            <target port="0" />
        </serial>
        <console type="pty">
            <target port="0" type="serial" />
        </console>
    </devices>''', xml)
