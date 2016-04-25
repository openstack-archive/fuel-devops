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

import mock

from devops.models import Environment
from devops.tests.driver.libvirt.base import LibvirtTestCase


class TestLibvirtNodeMultipath(LibvirtTestCase):

    def setUp(self):
        super(TestLibvirtNodeMultipath, self).setUp()

        self.sleep_mock = self.patch('devops.helpers.retry.sleep')
        self.libvirt_sleep_mock = self.patch(
            'devops.driver.libvirt.libvirt_driver.sleep')

        self.env = Environment.create('test_env')
        self.group = self.env.add_group(
            group_name='test_group',
            driver_name='devops.driver.libvirt.libvirt_driver',
            connection_string='test:///default',
            storage_pool_name='default-pool',
            vnc_password='123456',
        )

        self.ap = self.env.add_address_pool(
            name='test_ap',
            net='172.0.0.0/16:24',
            tag=0,
            ip_reserved=dict(l2_network_device=1),
        )

        self.net_pool = self.group.add_network_pool(
            name='fuelweb_admin',
            address_pool_name='test_ap',
        )

        self.l2_net_dev = self.group.add_l2_network_device(
            name='test_l2_net_dev',
            address_pool='test_ap',
            forward=dict(mode='nat'),
        )

        self.node = self.group.add_node(
            name='test_node',
            role='default',
            architecture='i686',
            hypervisor='test',
        )

        self.interface = self.node.add_interface(
            label='eth0',
            l2_network_device_name='test_l2_net_dev',
            interface_model='virtio',
        )
        self.interface.mac_address = '64:b6:87:44:14:17'
        self.interface.save()

        self.volume = self.node.add_volume(
            name='test_volume',
            capacity=5,
            multipath_count=2,
            serial='3b16d312420d4adbb2d5b04fcbd5221c',
        )

        self.d = self.group.driver

        self.l2_net_dev.define()
        self.volume.define()

    @mock.patch('devops.driver.libvirt.libvirt_driver.uuid')
    @mock.patch('libvirt.virConnect.defineXML')
    def test_define_xml(self, define_xml_mock, uuid_mock):
        uuid_mock.uuid4.side_effect = (
            mock.Mock(hex='fe527bd28e0f4a84b9117dc97142c580'),
            mock.Mock(hex='9cddb80fe82e480eb14c1a89f1c0e11d'))
        define_xml_mock.return_value.UUIDString.return_value = 'fake_uuid'

        self.node.define()
        assert define_xml_mock.call_count == 1
        xml = define_xml_mock.call_args[0][0]
        assert xml == """<?xml version="1.0" encoding="utf-8"?>
<domain type="test">
    <name>test_env_test_node</name>
    <cpu mode="host-passthrough"/>
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
        <type arch="i686">hvm</type>
        <boot dev="network"/>
        <boot dev="cdrom"/>
        <boot dev="hd"/>
    </os>
    <devices>
        <controller model="nec-xhci" type="usb"/>
        <emulator>/usr/bin/test-emulator</emulator>
        <graphics autoport="yes" listen="0.0.0.0" passwd="123456" type="vnc"/>
        <disk device="disk" type="file">
            <driver cache="unsafe" type="qcow2"/>
            <source file="/default-pool/test_env_test_node_test_volume"/>
            <target bus="scsi" dev="sda"/>
            <serial>3b16d312420d4adbb2d5b04fcbd5221c</serial>
            <wwn>0fe527bd28e0f4a8</wwn>
        </disk>
        <disk device="disk" type="file">
            <driver cache="unsafe" type="qcow2"/>
            <source file="/default-pool/test_env_test_node_test_volume"/>
            <target bus="scsi" dev="sdb"/>
            <serial>3b16d312420d4adbb2d5b04fcbd5221c</serial>
            <wwn>09cddb80fe82e480</wwn>
        </disk>
        <interface type="network">
            <mac address="64:b6:87:44:14:17"/>
            <source network="test_env_test_l2_net_dev"/>
            <target dev="virnet1"/>
            <model type="virtio"/>
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
