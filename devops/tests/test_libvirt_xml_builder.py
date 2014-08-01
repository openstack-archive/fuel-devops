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

from mock import Mock

from devops.driver.libvirt.libvirt_xml_builder import LibvirtXMLBuilder


class BaseTestXMLBuilder(TestCase):
    def setUp(self):
        self.xml_builder = LibvirtXMLBuilder(Mock())
        self.xml_builder.driver.volume_path = Mock(
            return_value="volume_path_mock"
        )
        self.xml_builder.driver.network_name = Mock(
            return_value="network_name_mock"
        )
        self.net = Mock()
        self.vol = Mock()
        self.node = Mock()


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
        bridge_name = 'dobr{0}'.format(self.net.id)
        xml = self.xml_builder.build_network_xml(self.net)
        self.assertIn(
            '<name>{0}_{1}</name>'
            ''.format(self.net.environment.name, self.net.name),
            xml)
        self.assertIn(
            '<bridge delay="0" name="{0}" stp="on" />'
            ''.format(bridge_name), xml)

    def test_forward(self):
        self.net.forward = "nat"
        xml = self.xml_builder.build_network_xml(self.net)
        self.assertIn(
            '<forward mode="{0}" />'
            ''.format(self.net.forward), xml)

    def test_ip_network(self):
        ip = '172.0.1.1'
        prefix = '24'
        self.net.ip_network = "{0}/{1}".format(ip, prefix)
        self.net.has_pxe_server = True
        self.net.tftp_root_dir = '/tmp'
        xml = self.xml_builder.build_network_xml(self.net)
        str = '''
    <ip address="{0}" prefix="{1}">
    </ip>'''.format(ip, prefix, self.net.tftp_root_dir)
        self.assertIn(str, xml)


class TestVolumeXml(BaseTestXMLBuilder):

    def setUp(self):
        super(TestVolumeXml, self).setUp()
        self.vol.name = 'test_name'
        self.vol.environment.name = 'test_env_name'
        self.vol.id = random.randint(1, 100)
        self.vol.format = "qcow2"
        self.vol.backing_store = None

    def test_general_properties(self):
        self.vol.capacity = random.randint(50, 100)
        xml = self.xml_builder.build_volume_xml(self.vol)
        self.assertIn(
            '<name>{0}_{1}</name>'
            ''.format(self.vol.environment.name, self.vol.name),
            xml)
        self.assertIn(
            '<capacity>{0}</capacity>'.format(self.vol.capacity), xml)
        self.assertIn(
            '''
    <target>
        <format type="{0}" />
    </target>'''.format(self.vol.format), xml)

    def test_backing_store(self):
        self.vol.backing_store = Mock(
            uuid="volume_uuid",
            format="raw"
        )
        xml = self.xml_builder.build_volume_xml(self.vol)
        self.assertIn(
            '''
    <backingStore>
        <path>volume_path_mock</path>
        <format type="{0}" />
    </backingStore>'''.format(self.vol.backing_store.format), xml)


class TestSnapshotXml(BaseTestXMLBuilder):

    def test_snapshot(self):
        name = 'test_snapshot'
        description = 'test_description'
        xml = self.xml_builder.build_snapshot_xml(name, description)
        self.assertIn(
            '''
<domainsnapshot>
    <name>{0}</name>
    <description>{1}</description>
</domainsnapshot>'''.format(name, description), xml)


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
        self.node.disk_devices = []
        self.node.interfaces = []

    def test_node(self):
        xml = self.xml_builder.build_node_xml(self.node, 'test_emulator')
        boot = json.loads(self.node.boot)
        self.assertIn('''
<domain type="test_hypervisor">
    <name>test_env_name_test_name</name>
    <cpu mode="host-model">
        <model fallback="forbid" />
    </cpu>
    <vcpu>{0}</vcpu>
    <memory unit="KiB">{1}</memory>
    <os>
        <type arch="{2}">{3}</type>
        <boot dev="{4}" />
        <boot dev="{5}" />
    </os>
    <devices>
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
                    boot[0], boot[1]), xml)

    def test_node_devices(self):
        volumes = [Mock(uuid=i, format='frmt{0}'.format(i)) for i in range(3)]
        self.node.disk_devices = [
            Mock(type='type{0}'.format(i), device='device{0}'.format(i),
                 volume=volumes[i], target_dev='tdev{0}'.format(i),
                 bus='bus{0}'.format(i)) for i in range(3)]
        xml = self.xml_builder.build_node_xml(self.node, 'test_emulator')
        self.assertIn('''
    <devices>
        <emulator>test_emulator</emulator>
        <disk device="device0" type="type0">
            <driver cache="unsafe" type="frmt0" />
            <source file="volume_path_mock" />
            <target bus="bus0" dev="tdev0" />
        </disk>
        <disk device="device1" type="type1">
            <driver cache="unsafe" type="frmt1" />
            <source file="volume_path_mock" />
            <target bus="bus1" dev="tdev1" />
        </disk>
        <disk device="device2" type="type2">
            <driver cache="unsafe" type="frmt2" />
            <source file="volume_path_mock" />
            <target bus="bus2" dev="tdev2" />
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
    </devices>''', xml)

    def test_node_interfaces(self):
        networks = [Mock(uuid=i) for i in range(3)]
        self.node.interfaces = [
            Mock(type='network'.format(i), mac_address='mac{0}'.format(i),
                 network=networks[i], id='id{0}'.format(i),
                 model='model{0}'.format(i)) for i in range(3)]
        xml = self.xml_builder.build_node_xml(self.node, 'test_emulator')
        self.assertIn('''
    <devices>
        <emulator>test_emulator</emulator>
        <interface type="network">
            <mac address="mac0" />
            <source network="network_name_mock" />
            <target dev="donetid0" />
            <model type="model0" />
        </interface>
        <interface type="network">
            <mac address="mac1" />
            <source network="network_name_mock" />
            <target dev="donetid1" />
            <model type="model1" />
        </interface>
        <interface type="network">
            <mac address="mac2" />
            <source network="network_name_mock" />
            <target dev="donetid2" />
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
