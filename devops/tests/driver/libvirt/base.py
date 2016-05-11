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


from django.test import TestCase
import mock


from devops.driver.libvirt.libvirt_driver import LibvirtManager

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


class LibvirtTestCase(TestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        self.libvirt_vol_up_mock = self.patch('libvirt.virStorageVol.upload')
        self.libvirt_stream_snd_mock = self.patch('libvirt.virStream.sendAll')
        self.libvirt_stream_fin_mock = self.patch('libvirt.virStream.finish')

        self.libvirt_nwfilter_define_mock = self.patch(
            'libvirt.virConnect.nwfilterDefineXML')
        self.libvirt_nwfilter_lookup_mock = self.patch(
            'libvirt.virConnect.nwfilterLookupByName')
        self.libvirt_list_all_devs_mock = self.patch(
            'libvirt.virConnect.listAllDevices')

        self._libvirt_clear_all()
        conn = LibvirtManager.get_connection('test:///default')

        self.caps_patcher = mock.patch.object(conn, 'getCapabilities')
        self.caps_mock = self.caps_patcher.start()
        self.addCleanup(self.caps_patcher.stop)
        self.caps_mock.return_value = CAPS_XML

    def tearDown(self):
        self._libvirt_clear_all()

    @staticmethod
    def _libvirt_clear_all():
        conn = LibvirtManager.get_connection('test:///default')
        pool = conn.storagePoolLookupByName('default-pool')

        for domain in conn.listAllDomains():
            for snapshot in domain.listAllSnapshots(0):
                snapshot.delete()
            domain.destroy()
            domain.undefine()
        for network in conn.listAllNetworks():
            network.destroy()
            network.undefine()
        for vol in pool.listAllVolumes():
            vol.delete()
