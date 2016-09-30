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

import re
# noinspection PyPep8Naming
import xml.etree.ElementTree as ET

import libvirt
import mock
import pytest

from devops.helpers.helpers import xml_tostring
from devops.models import Environment
from devops.tests.driver.libvirt.base import LibvirtTestCase


class TestLibvirtNode(LibvirtTestCase):

    def setUp(self):
        super(TestLibvirtNode, self).setUp()

        self.sleep_mock = self.patch('time.sleep')

        self.env = Environment.create('test_env')
        self.group = self.env.add_group(
            group_name='test_group',
            driver_name='devops.driver.libvirt',
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
            mac_address='64:b6:87:44:14:17',
            interface_model='virtio',
        )

        self.volume = self.node.add_volume(
            name='test_volume',
            capacity=5,
        )

        self.d = self.group.driver

        self.l2_net_dev.define()
        self.volume.define()

    @pytest.mark.xfail(reason="need libvirtd >= 1.2.12")
    def test_define_xml(self):
        self.node.define()
        xml = self.node._libvirt_node.XMLDesc(0)
        assert re.match(r"""<domain type='test'>
  <name>test_env_test_node</name>
  <uuid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}</uuid>
  <memory unit='KiB'>1048576</memory>
  <currentMemory unit='KiB'>1048576</currentMemory>
  <vcpu placement='static'>1</vcpu>
  <os>
    <type arch='i686'>hvm</type>
    <boot dev='network'/>
    <boot dev='cdrom'/>
    <boot dev='hd'/>
  </os>
  <cpu mode='host-passthrough'>
  </cpu>
  <clock offset='utc'>
    <timer name='rtc' tickpolicy='catchup' track='wall'>
      <catchup threshold='123' slew='120' limit='10000'/>
    </timer>
    <timer name='pit' tickpolicy='delay'/>
    <timer name='hpet' present='yes'/>
  </clock>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>destroy</on_crash>
  <devices>
    <emulator>/usr/bin/test-emulator</emulator>
    <disk type='file' device='disk'>
      <driver type='qcow2' cache='unsafe'/>
      <source file='/default-pool/test_env_test_node_test_volume'/>
      <target dev='sda' bus='virtio'/>
      <serial>[0-9a-f]{32}</serial>
    </disk>
    <controller type='usb' index='0' model='nec-xhci'/>
    <interface type='network'>
      <mac address='(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}'/>
      <source network='test_env_test_l2_net_dev'/>
      <target dev='virnet1'/>
      <model type='virtio'/>
    </interface>
    <serial type='pty'>
      <target port='0'/>
    </serial>
    <console type='pty'>
      <target type='serial' port='0'/>
    </console>
    <input type='mouse' bus='ps2'/>
    <input type='keyboard' bus='ps2'/>
    <graphics type='vnc' port='-1' autoport='yes' listen='0\.0\.0\.0'>
      <listen type='address' address='0\.0\.0\.0'/>
    </graphics>
    <video>
      <model type='vga' vram='16384' heads='1'/>
    </video>
  </devices>
</domain>
""", xml)

    @mock.patch('libvirt.virDomain.setMemoryFlags')
    @mock.patch('libvirt.virDomain.setMaxMemory')
    def test_set_memory(self, max_mem_mock, mem_flag_mock):
        self.node.define()
        assert self.node._libvirt_node.info()[2] == 1048576  # memory
        assert self.node.memory == 1024

        self.node.set_memory(64)
        max_mem_mock.assert_called_once_with(65536)
        mem_flag_mock.assert_called_once_with(65536, 2)

        node = self.group.get_node(name='test_node')
        assert node.memory == 64

    @mock.patch('libvirt.virDomain.setVcpusFlags')
    def test_set_vcpu(self, vcpu_mock):
        self.node.define()
        assert self.node._libvirt_node.info()[3] == 1  # cpu
        assert self.node.vcpu == 1

        self.node.set_vcpu(6)
        vcpu_mock.assert_has_calls((
            mock.call(6, 4),
            mock.call(6, 2),
        ))

        node = self.group.get_node(name='test_node')
        assert node.vcpu == 6

    def test_lifecycle(self):
        self.node.define()

        assert self.node.exists()
        assert not self.node.is_active()

        self.node.start()

        assert self.node.is_active()

        self.node.destroy()

        assert not self.node.is_active()
        assert self.node.exists()

        self.node.erase()

        assert not self.node.exists()

    def test_attrs(self):
        self.node.define()

        assert self.node.get_vnc_port() == '-1'
        assert self.node.vnc_password == '123456'

    def test_send_keys(self):
        self.node.define()
        self.node.start()

        with mock.patch('libvirt.virDomain.sendKey') as send_key:
            send_key.return_value = 0
            self.node.send_keys('123<Wait>\n<Enter>')
            send_key.assert_has_calls([
                mock.call(0, 0, [2], 1, 0),
                mock.call(0, 0, [3], 1, 0),
                mock.call(0, 0, [4], 1, 0),
                mock.call(0, 0, [28], 1, 0),
            ])
            self.sleep_mock.assert_called_once_with(1)

    def test_start_reboot(self):
        self.node.define()
        assert self.node.is_active() is False
        self.node.start()
        assert self.node.is_active() is True
        self.node.reboot()
        assert self.node.is_active() is True
        assert self.node._libvirt_node.info()[0] == libvirt.VIR_DOMAIN_RUNNING

    def test_start_shutdown(self):
        self.node.define()
        assert self.node.is_active() is False
        self.node.start()
        assert self.node.is_active() is True
        self.node.shutdown()
        assert self.node.is_active() is False
        assert self.node._libvirt_node.info()[0] == libvirt.VIR_DOMAIN_SHUTOFF

    def test_start_reset(self):
        self.node.define()
        assert self.node.is_active() is False
        self.node.start()
        assert self.node.is_active() is True
        # reset is not supported by libvirt test backend
        with mock.patch('libvirt.virDomain.reset') as reset_mock:
            self.node.reset()
            reset_mock.assert_called_once_with()

    def test_start_suspend_resume(self):
        self.node.define()
        assert self.node.is_active() is False
        self.node.start()
        assert self.node.is_active() is True
        self.node.suspend()
        assert self.node.is_active() is True
        assert self.node._libvirt_node.info()[0] == libvirt.VIR_DOMAIN_PAUSED
        self.node.resume()
        assert self.node.is_active() is True
        assert self.node._libvirt_node.info()[0] == libvirt.VIR_DOMAIN_RUNNING

    def test_get_target_dev(self):
        self.node.define()
        assert self.node.get_interface_target_dev(
            '64:b6:87:44:14:17') == 'testnet0'

    def test_set_boot(self):
        self.node.define()

        self.node.set_boot(['hd', 'cdrom'])
        assert self.node.boot == ['hd', 'cdrom']
        assert ("<os>\n"
                "    <type arch='i686'>hvm</type>\n"
                "    <boot dev='hd'/>\n"
                "    <boot dev='cdrom'/>\n"
                "  </os>\n") in self.node._libvirt_node.XMLDesc()

        self.node.set_boot(['cdrom', 'hd'])
        assert self.node.boot == ['cdrom', 'hd']
        assert ("<os>\n"
                "    <type arch='i686'>hvm</type>\n"
                "    <boot dev='cdrom'/>\n"
                "    <boot dev='hd'/>\n"
                "  </os>\n") in self.node._libvirt_node.XMLDesc()

    def test_close_tray(self):
        cdrom_volume = self.node.add_volume(
            name='test_iso',
            device='cdrom',
            capacity=5,
        )
        cdrom_volume.define()

        self.node.define()

        # open tray
        node_xml = ET.fromstring(self.node._libvirt_node.XMLDesc())
        node_xml.find(
            './devices/disk[@device="cdrom"]/target').attrib['tray'] = 'open'
        self.d.conn.defineXML(xml_tostring(node_xml))
        assert (
            "<target dev='sdb' bus='virtio' tray='open'/>"
        ) in self.node._libvirt_node.XMLDesc()

        self.node.close_tray()
        assert (
            "<target dev='sdb' bus='virtio'/>"
        ) in self.node._libvirt_node.XMLDesc()
