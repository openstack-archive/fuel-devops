#    Copyright 2015 Mirantis, Inc.
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

from django.test import TestCase
import mock

from devops.models import Environment

CAPS_XML = """
<capabilities>

  <host>
    <cpu>
      <arch>i686</arch>
      <features>
        <pae/>
        <nonpae/>
      </features>
    </cpu>
    <power_management/>
    <secmodel>
      <model>testSecurity</model>
      <doi></doi>
    </secmodel>
  </host>

  <guest>
    <os_type>hvm</os_type>
    <arch name='i686'>
      <wordsize>32</wordsize>
      <emulator>/usr/bin/qemu-system-i386</emulator>
      <domain type='qemu'>
      </domain>
      <domain type='test'>
        <emulator>/usr/bin/test-emulator</emulator>
      </domain>
    </arch>
    <features>
      <cpuselection/>
      <deviceboot/>
      <acpi default='on' toggle='yes'/>
      <apic default='on' toggle='no'/>
      <pae/>
      <nonpae/>
    </features>
  </guest>

  <guest>
    <os_type>hvm</os_type>
    <arch name='x86_64'>
      <wordsize>64</wordsize>
      <emulator>/usr/bin/qemu-system-x86_64</emulator>
      <domain type='test'>
        <emulator>/usr/bin/test-emulator</emulator>
      </domain>
    </arch>
    <features>
      <cpuselection/>
      <deviceboot/>
      <acpi default='on' toggle='yes'/>
      <apic default='on' toggle='no'/>
    </features>
  </guest>

</capabilities>
"""


class TestLibvirtL2NetworkDevice(TestCase):

    def setUp(self):
        self.sleep_patcher = mock.patch('devops.helpers.retry.sleep')
        self.sleep_mock = self.sleep_patcher.start()

        self.env = Environment.create('test_env')
        self.group = self.env.add_group(
            group_name='test_group',
            driver_name='devops.driver.libvirt.libvirt_driver',
            connection_string='test:///default',
            storage_pool_name='default-pool')

        self.ap = self.env.add_address_pool(
            name='test_ap',
            net='172.0.0.0/16:24',
            tag=0,
        )

        self.net_pool = self.group.add_network_pool(
            name='fuelweb_admin',
            address_pool_name='test_ap',
        )

        self.l2_net_dev = self.group.add_l2_network_device(
            name='test_l2_net_dev',
            address_pool_name='test_ap',
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

        self.volume = self.node.add_volume(
            name='test_volume',
            capacity=512,
        )

        self.d = self.group.driver

        self.caps_patcher = mock.patch.object(self.d.conn, 'getCapabilities')
        self.caps_mock = self.caps_patcher.start()

        self.caps_mock.return_value = CAPS_XML

        self.l2_net_dev.define()
        self.volume.define()

    def tearDown(self):
        # undefine all networks
        for network_name in self.d.conn.listDefinedNetworks():
            self.d.conn.networkLookupByName(network_name).undefine()

        self.sleep_patcher.stop()
        self.caps_patcher.stop()

    def test_define(self):
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
      <model type='vga' vram='9216' heads='1'/>
    </video>
  </devices>
</domain>
""", xml)
