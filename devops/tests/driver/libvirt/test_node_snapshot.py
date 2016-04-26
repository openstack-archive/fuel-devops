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
import xml.etree.ElementTree as ET

import libvirt
import mock
import pytest

from devops.error import DevopsError
from devops.models import Environment
from devops.models import Volume
from devops.tests.driver.libvirt.base import LibvirtTestCase


class TestLibvirtNodeSnapshotBase(LibvirtTestCase):

    def setUp(self):
        super(TestLibvirtNodeSnapshotBase, self).setUp()

        self.sleep_mock = self.patch('devops.helpers.retry.sleep')
        self.libvirt_sleep_mock = self.patch(
            'devops.driver.libvirt.libvirt_driver.sleep')

        self.nwfilter = self.libvirt_nwfilter_lookup_mock.return_value
        self.nwfilter.XMLDesc.return_value = (
            '<?xml version="1.0" encoding="utf-8" ?>\n'
            '<filter name="tenv_test_l2_net_dev_64:5d:8b:a9:ac:ec">\n'
            '    <filterref filter="tenv_test_l2_net_dev" />\n'
            '    <rule action="drop" direction="inout" priority="-950">\n'
            '        <all />\n'
            '    </rule>\n'
            '</filter>'
        )
        self.nwfilter.UUIDString.return_value = \
            'e3db79b5-717c-4b15-9198-ecad569c1ea2'

        self.env = Environment.create('tenv')
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
            ip_reserved=dict(l2_network_device='172.0.0.1'),
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
            name='tnode',
            role='default',
            architecture='i686',
            hypervisor='test',
        )

        self.interface = self.node.add_interface(
            label='eth0',
            l2_network_device_name='test_l2_net_dev',
            interface_model='virtio',
        )
        self.interface.mac_address = '64:5d:8b:a9:ac:ec'
        self.interface.save()

        self.volume = self.node.add_volume(
            name='tvol',
            capacity=5,
        )

        self.d = self.group.driver

        self.l2_net_dev.define()
        self.volume.define()
        self.node.define()


class TestLibvirtNodeSnapshot(TestLibvirtNodeSnapshotBase):

    def setUp(self):
        super(TestLibvirtNodeSnapshot, self).setUp()

        self.os_mock = self.patch('devops.driver.libvirt.libvirt_driver.os')

    @pytest.mark.xfail(reason="need libvirtd >= 1.2.12")
    def test_snapshot_class(self):
        self.node.snapshot(name='test1')
        assert self.node.has_snapshot('test1')
        assert len(self.node.get_snapshots()) == 1

        snapshot = self.node.get_snapshots()[0]

        assert snapshot.children_num == 0
        assert snapshot.created
        assert snapshot.disks == {}
        assert snapshot.get_type == 'internal'
        assert snapshot.memory_file is None
        assert snapshot.name == 'test1'
        with self.assertRaises(libvirt.libvirtError):
            snapshot.parent
        assert snapshot.state == 'shutoff'

        rxml = r"""<domainsnapshot>
  <name>test1</name>
  <state>shutoff</state>
  <creationTime>\d+</creationTime>
  <memory snapshot="no" />
  <disks>
    <disk name="sda" snapshot="internal" />
  </disks>
  <domain type="test">
    <name>tenv_tnode</name>
    <uuid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}</uuid>
    <memory unit="KiB">1048576</memory>
    <currentMemory unit="KiB">1048576</currentMemory>
    <vcpu placement="static">1</vcpu>
    <os>
      <type arch="i686">hvm</type>
      <boot dev="network" />
      <boot dev="cdrom" />
      <boot dev="hd" />
    </os>
    <clock offset="utc">
      <timer name="rtc" tickpolicy="catchup" track="wall">
        <catchup limit="10000" slew="120" threshold="123" />
      </timer>
      <timer name="pit" tickpolicy="delay" />
      <timer name="hpet" present="yes" />
    </clock>
    <on_poweroff>destroy</on_poweroff>
    <on_reboot>restart</on_reboot>
    <on_crash>destroy</on_crash>
    <devices>
      <emulator>/usr/bin/test-emulator</emulator>
      <disk device="disk" type="file">
        <driver cache="unsafe" type="qcow2" />
        <source file="/default-pool/tenv_tnode_tvol" />
        <target bus="virtio" dev="sda" />
        <serial>[0-9a-f]{32}</serial>
      </disk>
      <controller index="0" model="nec-xhci" type="usb" />
      <interface type="network">
        <mac address="(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}" />
        <source network="tenv_test_l2_net_dev" />
        <target dev="virnet1" />
        <model type="virtio" />
      </interface>
      <serial type="pty">
        <target port="0" />
      </serial>
      <console type="pty">
        <target port="0" type="serial" />
      </console>
      <input bus="ps2" type="mouse" />
      <input bus="ps2" type="keyboard" />
      <graphics autoport="yes" listen="0\.0\.0\.0" port="-1" type="vnc">
        <listen address="0\.0\.0\.0" type="address" />
      </graphics>
      <video>
        <model heads="1" type="vga" vram="16384" />
      </video>
    </devices>
  <cpu mode="host-passthrough">
  </cpu>
  </domain>
</domainsnapshot>"""
        assert re.match(rxml, snapshot.xml)

        self.node.start()
        self.node.snapshot(name='test2')
        assert self.node.has_snapshot('test2')
        assert len(self.node.get_snapshots()) == 2
        snapshot2 = self.node._get_snapshot('test2')
        assert snapshot2.name == 'test2'
        assert snapshot2.state == 'running'

    def test_snapshot_basics(self):
        self.node.snapshot(name='test1')
        assert self.node.has_snapshot('test1')
        assert len(self.node.get_snapshots()) == 1
        self.node.snapshot(name='test2')
        assert self.node.has_snapshot('test2')
        assert len(self.node.get_snapshots()) == 2
        self.node.snapshot(name='test3')
        assert self.node.has_snapshot('test3')
        assert len(self.node.get_snapshots()) == 3

        with self.assertRaises(DevopsError):
            self.node.snapshot(name='test1')
        assert self.node.has_snapshot('test1')
        assert len(self.node.get_snapshots()) == 3

        self.node.snapshot(name='test1', force=True)
        assert self.node.has_snapshot('test1')
        assert len(self.node.get_snapshots()) == 3

        self.node.erase_snapshot('test1')
        assert self.node.has_snapshot('test1') is False
        assert self.node.has_snapshot('test2')
        assert self.node.has_snapshot('test3')
        assert len(self.node.get_snapshots()) == 2
        self.node.erase_snapshot('test2')
        assert self.node.has_snapshot('test1') is False
        assert self.node.has_snapshot('test2') is False
        assert self.node.has_snapshot('test3')
        assert len(self.node.get_snapshots()) == 1
        self.node.erase_snapshot('test3')
        assert self.node.has_snapshot('test1') is False
        assert self.node.has_snapshot('test2') is False
        assert self.node.has_snapshot('test3') is False
        assert len(self.node.get_snapshots()) == 0

    def test_remove_node_with_snapshot(self):
        self.node.snapshot(name='test1')
        assert self.node.has_snapshot('test1')
        assert len(self.node.get_snapshots()) == 1
        assert len(self.d.conn.listAllDomains()) == 1
        self.node.remove()
        assert len(self.d.conn.listAllDomains()) == 0

    def test_delete_snaphost_files(self):
        self.node.start()
        self.node.snapshot(name='test1')

        snap = self.node._get_snapshot('test1')
        self.node._delete_snapshot_files(snap)

        assert self.os_mock.remove.called is False

    def test_revert(self):
        with self.assertRaises(DevopsError):
            self.node.revert(name='test1')

        self.node.start()
        self.node.snapshot(name='test1')

        with mock.patch('libvirt.virDomain.revertToSnapshot') as rev_mock:
            self.node.revert(name='test1')
            assert rev_mock.called

    def test_revert_block(self):
        with self.assertRaises(DevopsError):
            self.node.revert(name='test1')

        self.node.start()
        self.node.snapshot(name='test1')
        self.interface.block()

        self.libvirt_nwfilter_define_mock.reset_mock()
        with mock.patch('libvirt.virDomain.revertToSnapshot') as rev_mock:
            self.node.revert(name='test1')
            assert rev_mock.called
            self.libvirt_nwfilter_define_mock.assert_called_once_with(
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<filter name="tenv_test_l2_net_dev_64:5d:8b:a9:ac:ec">\n'
                '    <filterref filter="tenv_test_l2_net_dev"/>\n'
                '    <uuid>e3db79b5-717c-4b15-9198-ecad569c1ea2</uuid>\n'
                '</filter>\n'
            )

    def test_revert_destroy(self):
        self.node.start()
        self.node.snapshot(name='test1')

        with mock.patch('libvirt.virDomain.destroy') as dest_mock:
            self.node.revert(name='test1')
            dest_mock.assert_called_once_with()


@pytest.mark.xfail(reason="need libvirtd >= 1.2.12")
class TestLibvirtNodeExternalSnapshot(TestLibvirtNodeSnapshotBase):

    def setUp(self):
        super(TestLibvirtNodeExternalSnapshot, self).setUp()

        self.snap_create_xml_mock = self.patch(
            'libvirt.virDomain.snapshotCreateXML')
        self.snap_lookup_mock = self.patch(
            'libvirt.virDomain.snapshotLookupByName')
        self.snap_mocks_dict = dict()
        self.snap_xmls_dict = dict()

        def add_snap(xml, flags=0):
            name = ET.fromstring(xml).find('name').text
            if name in self.snap_mocks_dict:
                return
            snap_mock = mock.Mock(spec=libvirt.virDomainSnapshot)
            snap_mock.numChildren.return_value = 0
            snap_mock.getXMLDesc.return_value = self.snap_xmls_dict[name]
            snap_mock.getDomain.return_value = self.node._libvirt_node
            self.snap_mocks_dict[name] = snap_mock

        self.snap_create_xml_mock.side_effect = add_snap

        def lookup_by_name(name, flags=0):
            return self.snap_mocks_dict[name]
        self.snap_lookup_mock.side_effect = lookup_by_name
        self.snap_names_mock = self.patch(
            'libvirt.virDomain.snapshotListNames')
        self.snap_names_mock.side_effect = self.snap_mocks_dict.keys

        self.settings_mock = self.patch(
            'devops.driver.libvirt.libvirt_driver.settings')
        self.settings_mock.SNAPSHOTS_EXTERNAL_DIR = '/tmp/snap'

        self.def_xml_mock = self.patch('libvirt.virConnect.defineXML')

        self.os_mock = self.patch('devops.driver.libvirt.libvirt_driver.os')
        self.exists_dict = {
            '/tmp/snap/': False,
            '/tmp/snap/snapshot-memory-tenv_tnode.test1': True,
            '/tmp/snap/snapshot-memory-tenv_tnode.test1-0': True,
        }
        self.os_mock.path.exists.side_effect = self.exists_dict.get
        self.is_file_dict = {
            '/tmp/snap/snapshot-memory-tenv_tnode.test1': True,
        }
        self.os_mock.path.isfile.side_effect = self.is_file_dict.get

    def test_snapshot_incorrect_libvirt_version(self):
        ver_mcok = self.patch('libvirt.virConnect.getLibVersion')
        ver_mcok.return_value = 1002011
        with self.assertRaises(DevopsError):
            self.node.snapshot(name='test1', external=True)

    def test_create_external_snapshot_inactive(self):
        self.snap_xmls_dict['test1'] = (
            '<domainsnapshot>\n'
            '    <name>test1</name>\n'
            '    <memory snapshot="no" />\n'
            '    <disks>\n'
            '        <disk file="/default-pool/'
            'tenv_tnode_tvol.test1" name="sda" '
            'snapshot="external" />\n'
            '    </disks>\n'
            '    <domain>\n'
            '        <cpu mode="host-model" />\n'
            '    </domain>\n'
            '</domainsnapshot>')

        self.node.snapshot(name='test1', external=True)

        assert len(self.snap_create_xml_mock.mock_calls) == 2

        xml = ('<?xml version="1.0" encoding="utf-8" ?>\n'
               '<domainsnapshot>\n'
               '    <name>test1</name>\n'
               '    <memory snapshot="no" />\n'
               '    <disks>\n'
               '        <disk file="/default-pool/'
               'tenv_tnode_tvol.test1" name="sda" '
               'snapshot="external" />\n'
               '    </disks>\n'
               '</domainsnapshot>')
        xml1 = ('<domainsnapshot>\n'
                '    <name>test1</name>\n'
                '    <memory snapshot="no" />\n'
                '    <disks>\n'
                '        <disk '
                'file="/default-pool/tenv_tnode_tvol.test1" '
                'name="sda" snapshot="external" />\n'
                '    </disks>\n'
                '    <domain>\n'
                '        <cpu mode="host-model" />\n'
                '    </domain>\n'
                '</domainsnapshot>')

        self.snap_create_xml_mock.assert_has_calls([
            mock.call(xml,
                      (libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_DISK_ONLY |
                       libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REUSE_EXT)),
            mock.call(xml1,
                      (libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE |
                       libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT)),
        ])

        self.os_mock.makedirs.assert_called_once_with('/tmp/snap')

    def test_create_external_snapshot_active(self):
        self.snap_xmls_dict['test1'] = (
            '<domainsnapshot>\n'
            '    <name>test1</name>\n'
            '    <memory snapshot="no" />\n'
            '    <disks>\n'
            '        <disk file="/default-pool/'
            'tenv_tnode_tvol.test1" name="sda" '
            'snapshot="external" />\n'
            '    </disks>\n'
            '    <domain>\n'
            '        <cpu mode="host-model" />\n'
            '    </domain>\n'
            '</domainsnapshot>')

        pool = self.d.conn.storagePoolLookupByName('default-pool')
        assert len(pool.listAllVolumes()) == 1

        self.node.start()
        self.node.snapshot(name='test1', external=True)

        assert len(pool.listAllVolumes()) == 2
        assert len(self.snap_create_xml_mock.mock_calls) == 2

        xml = ('<?xml version="1.0" encoding="utf-8" ?>\n'
               '<domainsnapshot>\n'
               '    <name>test1</name>\n'
               '    <memory file="/tmp/snap/'
               'snapshot-memory-tenv_tnode.test1-1" '
               'snapshot="external" />\n'
               '    <disks>\n'
               '        <disk file="/default-pool/'
               'tenv_tnode_tvol.test1" name="sda" '
               'snapshot="external" />\n'
               '    </disks>\n'
               '</domainsnapshot>')
        xml1 = ('<domainsnapshot>\n'
                '    <name>test1</name>\n'
                '    <memory snapshot="no" />\n'
                '    <disks>\n'
                '        <disk '
                'file="/default-pool/tenv_tnode_tvol.test1" name="sda" '
                'snapshot="external" />\n'
                '    </disks>\n'
                '    <domain>\n'
                '        <cpu mode="host-model" />\n'
                '    </domain>\n'
                '</domainsnapshot>')
        self.snap_create_xml_mock.assert_has_calls([
            mock.call(xml, libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REUSE_EXT),
            mock.call(xml1,
                      (libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE |
                       libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT)),
        ])

        self.os_mock.makedirs.assert_called_once_with('/tmp/snap')

        main_vol = self.node.get_volume(name='tvol')
        assert main_vol
        snap_vol = self.node.get_volume(name='tvol.test1')
        assert snap_vol
        assert snap_vol.backing_store.id == main_vol.id

    def test_set_snapshot_current(self):
        self.snap_xmls_dict['test1'] = (
            '<domainsnapshot>\n'
            '    <name>test1</name>\n'
            '    <memory snapshot="no" />\n'
            '    <disks>\n'
            '        <disk file="/default-pool/'
            'tenv_tnode_tvol.test1" name="sda" '
            'snapshot="external" />\n'
            '    </disks>\n'
            '    <domain>\n'
            '        <cpu mode="host-model" />\n'
            '    </domain>\n'
            '</domainsnapshot>')

        self.node.snapshot(name='test1', external=True)
        self.snap_create_xml_mock.reset_mock()

        xml1 = ('<domainsnapshot>\n'
                '    <name>test1</name>\n'
                '    <memory snapshot="no" />\n'
                '    <disks>\n'
                '        <disk '
                'file="/default-pool/tenv_tnode_tvol.test1" name="sda" '
                'snapshot="external" />\n'
                '    </disks>\n'
                '    <domain>\n'
                '        <cpu mode="host-model" />\n'
                '    </domain>\n'
                '</domainsnapshot>')

        self.node.set_snapshot_current(name='test1')
        self.snap_create_xml_mock.assert_called_once_with(
            xml1,
            (libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE |
             libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT),
        )

    def test_set_snapshot_current_host_passthrough(self):
        self.snap_xmls_dict['test1'] = (
            '<domainsnapshot>\n'
            '    <name>test1</name>\n'
            '    <memory snapshot="no" />\n'
            '    <disks>\n'
            '        <disk file="/default-pool/'
            'tenv_tnode_tvol.test1" name="sda" '
            'snapshot="external" />\n'
            '    </disks>\n'
            '    <domain>\n'
            '        <cpu mode="host-passthrough" />\n'
            '    </domain>\n'
            '</domainsnapshot>')

        self.node.snapshot(name='test1', external=True)
        self.snap_create_xml_mock.reset_mock()

        xml1 = (
            '<domainsnapshot>\n'
            '    <name>test1</name>\n'
            '    <memory snapshot="no" />\n'
            '    <disks>\n'
            '        <disk file="/default-pool/tenv_tnode_tvol.test1" '
            'name="sda" snapshot="external" />\n'
            '    </disks>\n'
            '    <domain>\n'
            '        <cpu mode="host-passthrough">\n'
            '  </cpu>\n'
            '  </domain>\n'
            '</domainsnapshot>')

        self.node.set_snapshot_current(name='test1')
        self.snap_create_xml_mock.assert_called_once_with(
            xml1,
            (libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE |
             libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT),
        )

    def test_erase_snapshot(self):
        self.snap_xmls_dict['test1'] = (
            '<domainsnapshot>\n'
            '    <name>test1</name>\n'
            '    <memory file="/tmp/snap/'
            'snapshot-memory-tenv_tnode.test1" '
            'snapshot="external"/>\n'
            '    <domain>\n'
            '        <cpu mode="host-model" />\n'
            '    </domain>\n'
            '</domainsnapshot>')

        pool = self.d.conn.storagePoolLookupByName('default-pool')
        assert len(pool.listAllVolumes()) == 1
        assert self.node.get_volume(name='tvol')

        self.node.start()
        self.node.snapshot(name='test1', external=True)

        assert len(pool.listAllVolumes()) == 2
        assert self.node.get_volume(name='tvol')
        assert self.node.get_volume(name='tvol.test1')

        self.snap_create_xml_mock.reset_mock()
        snap_mock = self.snap_mocks_dict['test1']
        snap_mock.numChildren.return_value = 0

        self.node.erase_snapshot('test1')
        self.def_xml_mock.assert_called_once_with(
            '<domain>\n'
            '        <cpu mode="host-model" />\n'
            '    </domain>\n')
        snap_mock.delete.assert_called_once_with(2)

        assert len(pool.listAllVolumes()) == 1
        assert self.node.get_volume(name='tvol')
        with self.assertRaises(Volume.DoesNotExist):
            self.node.get_volume(name='tvol.test1')

        self.os_mock.remove.assert_called_once_with(
            '/tmp/snap/snapshot-memory-tenv_tnode.test1')

    def test_delete_snaphost_files(self):
        self.snap_xmls_dict['test1'] = (
            '<domainsnapshot>\n'
            '    <name>test1</name>\n'
            '    <memory file="/tmp/snap/'
            'snapshot-memory-tenv_tnode.test1" '
            'snapshot="external"/>\n'
            '    <domain>\n'
            '        <cpu mode="host-model" />\n'
            '    </domain>\n'
            '</domainsnapshot>')

        self.node.start()
        self.node.snapshot(name='test1', external=True)

        self.snap_create_xml_mock.reset_mock()
        snap_mock = self.snap_mocks_dict['test1']
        snap_mock.numChildren.return_value = 0

        snap = self.node._get_snapshot('test1')
        self.node._delete_snapshot_files(snap)

        self.os_mock.remove.assert_called_once_with(
            '/tmp/snap/snapshot-memory-tenv_tnode.test1')

    def test_erase_snapshot_has_children(self):
        self.snap_xmls_dict['test1'] = (
            '<domainsnapshot>\n'
            '    <name>test1</name>\n'
            '    <memory file="/tmp/snap/'
            'snapshot-memory-tenv_tnode.test1" '
            'snapshot="external"/>\n'
            '    <domain>\n'
            '        <cpu mode="host-model" />\n'
            '    </domain>\n'
            '</domainsnapshot>')

        pool = self.d.conn.storagePoolLookupByName('default-pool')

        assert len(pool.listAllVolumes()) == 1
        assert self.node.get_volume(name='tvol')

        self.node.start()
        self.node.snapshot(name='test1', external=True)

        self.snap_create_xml_mock.reset_mock()
        snap_mock = self.snap_mocks_dict['test1']
        snap_mock.numChildren.return_value = 1

        assert len(pool.listAllVolumes()) == 2
        assert self.node.get_volume(name='tvol')
        assert self.node.get_volume(name='tvol.test1')

        self.node.erase_snapshot('test1')

        assert len(pool.listAllVolumes()) == 2
        assert self.node.get_volume(name='tvol')
        assert self.node.get_volume(name='tvol.test1')
        assert self.os_mock.remove.called is False

    def test_erase_snapshot_domain(self):
        self.snap_xmls_dict['test1'] = """<domainsnapshot>
  <name>test1</name>
  <memory snapshot="external"/>
  <disks/>
  <domain>
    <name>tnode</name>
    <devices>
      <disk type='file' device='disk' snapshot='external'>
        <driver name='qemu' type='raw'/>
        <source file='/tmp/file1'/>
        <target dev='vda' bus='virtio'/>
      </disk>
      <disk type='file' device='disk' snapshot='external'>
        <driver name='qemu' type='raw'/>
        <source file='/tmp/file2'/>
        <target dev='vdb' bus='virtio'/>
      </disk>
    </devices>
    <cpu mode="host-model" />
  </domain>
</domainsnapshot>"""

        self.node.start()
        self.node.snapshot(name='test1', external=True)

        self.snap_create_xml_mock.reset_mock()
        snap_mock = self.snap_mocks_dict['test1']
        snap_mock.numChildren.return_value = 0

        self.node.erase_snapshot('test1')

        self.def_xml_mock.assert_called_once_with("""<domain>
    <name>tnode</name>
    <devices>
      <disk device="disk" snapshot="external" type="file">
        <driver name="qemu" type="raw" />
        <source file="/tmp/file1" />
        <target bus="virtio" dev="vda" />
      </disk>
      <disk device="disk" snapshot="external" type="file">
        <driver name="qemu" type="raw" />
        <source file="/tmp/file2" />
        <target bus="virtio" dev="vdb" />
      </disk>
    </devices>
    <cpu mode="host-model" />
  </domain>
""")
        snap_mock.delete.assert_called_once_with(2)

    def test_revert_snapshot_has_no_children(self):
        self.snap_xmls_dict['test1'] = """<domainsnapshot>
  <name>test1</name>
  <state>shutoff</state>
  <memory snapshot="no"/>
  <disks>
    <disk name='sda' snapshot='external'>
      <source file='/default-pool/tenv_tnode_tvol'/>
    </disk>
  </disks>
  <domain type="test">
    <name>tnode</name>
    <devices>
      <disk type='file' device='disk' snapshot='external'>
        <driver name='qemu' type='raw'/>
        <source file='/default-pool/tenv_tnode_tvol'/>
        <target dev='sda' bus='virtio'/>
      </disk>
    </devices>
    <cpu mode="host-model" />
  </domain>
</domainsnapshot>"""

        self.node.start()

        assert self.node.disk_devices[0].volume.name == 'tvol'

        self.node.snapshot(name='test1', external=True)

        self.snap_create_xml_mock.reset_mock()
        snap_mock = self.snap_mocks_dict['test1']
        snap_mock.numChildren.return_value = 0

        assert self.node.disk_devices[0].volume.name == 'tvol.test1'

        vol_del_mock = self.patch('libvirt.virStorageVol.delete')
        pool_crt_mock = self.patch('libvirt.virStoragePool.createXML')

        self.node.revert(name='test1')

        self.def_xml_mock.assert_called_once_with("""<domain type="test">
    <name>tnode</name>
    <devices>
      <disk device="disk" snapshot="external" type="file">
        <driver name="qemu" type="raw" />
        <source file="/default-pool/tenv_tnode_tvol" />
        <target bus="virtio" dev="sda" />
      </disk>
    </devices>
    <cpu mode="host-model" />
  </domain>
""")
        assert self.node.disk_devices[0].volume.name == 'tvol'
        vol_del_mock.assert_called_once_with()
        pool_crt_mock.assert_called_once_with("""<volume type='file'>
  <name>tenv_tnode_tvol</name>
  <key>/default-pool/tenv_tnode_tvol</key>
  <source>
  </source>
  <capacity unit='bytes'>512</capacity>
  <allocation unit='bytes'>512</allocation>
  <target>
    <path>/default-pool/tenv_tnode_tvol</path>
    <format type='qcow2'/>
    <permissions>
      <mode>0600</mode>
      <owner>-1</owner>
      <group>-1</group>
    </permissions>
  </target>
</volume>
""")

    def test_revert_snapshot_has_no_children_not_shutoff(self):
        self.snap_xmls_dict['test1'] = """<domainsnapshot>
  <name>test1</name>
  <state>running</state>
  <memory file='/tmp/memfile' snapshot='external'/>
  <disks>
    <disk name='sda' snapshot='external'>
      <source file='/default-pool/tenv_tnode_tvol'/>
    </disk>
  </disks>
  <domain type="test">
    <name>tnode</name>
    <devices>
      <disk type='file' device='disk' snapshot='external'>
        <driver name='qemu' type='raw'/>
        <source file='/default-pool/tenv_tnode_tvol'/>
        <target dev='sda' bus='virtio'/>
      </disk>
    </devices>
    <cpu mode="host-model" />
  </domain>
</domainsnapshot>"""

        self.node.start()

        assert self.node.disk_devices[0].volume.name == 'tvol'

        self.node.snapshot(name='test1', external=True)

        self.snap_create_xml_mock.reset_mock()
        snap_mock = mock.Mock(spec=libvirt.virDomainSnapshot)
        self.snap_mocks_dict['test1'] = snap_mock
        snap_mock.numChildren.return_value = 0
        snapshot_xml = """<domainsnapshot>
  <name>test1</name>
  <state>running</state>
  <memory file='/tmp/memfile' snapshot='external'/>
  <disks>
    <disk name='sda' snapshot='external'>
      <source file='/default-pool/tenv_tnode_tvol'/>
    </disk>
  </disks>
  <domain type="test">
    <name>tnode</name>
    <devices>
      <disk type='file' device='disk' snapshot='external'>
        <driver name='qemu' type='raw'/>
        <source file='/default-pool/tenv_tnode_tvol'/>
        <target dev='sda' bus='virtio'/>
      </disk>
    </devices>
    <cpu mode="host-model" />
  </domain>
</domainsnapshot>"""
        snap_mock.getXMLDesc.return_value = snapshot_xml

        assert self.node.disk_devices[0].volume.name == 'tvol.test1'

        vol_del_mock = self.patch('libvirt.virStorageVol.delete')
        pool_crt_mock = self.patch('libvirt.virStoragePool.createXML')
        conn_rstflg_mock = self.patch('libvirt.virConnect.restoreFlags')

        self.node.revert(name='test1')

        dom_xml = """<domain type="test">
    <name>tnode</name>
    <devices>
      <disk device="disk" snapshot="external" type="file">
        <driver name="qemu" type="raw" />
        <source file="/default-pool/tenv_tnode_tvol" />
        <target bus="virtio" dev="sda" />
      </disk>
    </devices>
    <cpu mode="host-model" />
  </domain>
"""
        conn_rstflg_mock.assert_called_once_with(
            '/tmp/memfile',
            dxml=dom_xml,
            flags=libvirt.VIR_DOMAIN_SAVE_PAUSED)

        assert self.node.disk_devices[0].volume.name == 'tvol'
        vol_del_mock.assert_called_once_with()
        pool_crt_mock.assert_called_once_with("""<volume type='file'>
  <name>tenv_tnode_tvol</name>
  <key>/default-pool/tenv_tnode_tvol</key>
  <source>
  </source>
  <capacity unit='bytes'>512</capacity>
  <allocation unit='bytes'>512</allocation>
  <target>
    <path>/default-pool/tenv_tnode_tvol</path>
    <format type='qcow2'/>
    <permissions>
      <mode>0600</mode>
      <owner>-1</owner>
      <group>-1</group>
    </permissions>
  </target>
</volume>
""")

    def test_revert_snapshot_has_children(self):
        snap1_xml = """<domainsnapshot>
  <name>test1</name>
  <state>shutoff</state>
  <memory snapshot="no"/>
  <disks>
    <disk name='sda' snapshot='external'>
      <source file='/default-pool/tenv_tnode_tvol.test1'/>
    </disk>
  </disks>
  <domain type="test">
    <name>tnode</name>
    <devices>
      <disk type='file' device='disk' snapshot='external'>
        <driver name='qemu' type='raw'/>
        <source file='/default-pool/tenv_tnode_tvol.test1'/>
        <target dev='sda' bus='virtio'/>
      </disk>
    </devices>
    <cpu mode="host-model" />
  </domain>
</domainsnapshot>"""
        self.snap_xmls_dict['test1'] = snap1_xml

        snap2_xml = """<domainsnapshot>
  <name>test2</name>
  <state>shutoff</state>
  <memory snapshot="no"/>
  <disks>
    <disk name='sda' snapshot='external'>
      <source file='/default-pool/tenv_tnode_tvol.test2'/>
    </disk>
  </disks>
  <domain type="test">
    <name>tnode</name>
    <devices>
      <disk type='file' device='disk' snapshot='external'>
        <driver name='qemu' type='raw'/>
        <source file='/default-pool/tenv_tnode_tvol.test2'/>
        <target dev='sda' bus='virtio'/>
      </disk>
    </devices>
    <cpu mode="host-model" />
  </domain>
</domainsnapshot>"""
        self.snap_xmls_dict['test2'] = snap2_xml

        snap3_xml = """<domainsnapshot>
  <name>test2</name>
  <state>shutoff</state>
  <memory snapshot="no"/>
  <disks>
    <disk name='sda' snapshot='external'>
      <source file='/default-pool/tenv_tnode_tvol.test2'/>
    </disk>
  </disks>
  <domain type="test">
    <name>tnode</name>
    <devices>
      <disk type='file' device='disk' snapshot='external'>
        <driver name='qemu' type='raw'/>
        <source file='/default-pool/tenv_tnode_tvol.test2'/>
        <target dev='sda' bus='virtio'/>
      </disk>
    </devices>
    <cpu mode="host-model" />
  </domain>
</domainsnapshot>"""
        self.snap_xmls_dict['test3'] = snap3_xml

        snap1r_xml = """<domainsnapshot>
  <name>test1-revert</name>
  <state>shutoff</state>
  <memory snapshot="no"/>
  <disks>
    <disk name='sda' snapshot='external'>
      <source file='/default-pool/tenv_tnode_tvol.test1-revert'/>
    </disk>
  </disks>
  <domain type="test">
    <name>tnode</name>
    <devices>
      <disk type='file' device='disk' snapshot='external'>
        <driver name='qemu' type='raw'/>
        <source file='/default-pool/tenv_tnode_tvol.test1-revert'/>
        <target dev='sda' bus='virtio'/>
      </disk>
    </devices>
    <cpu mode="host-model" />
  </domain>
</domainsnapshot>"""
        self.snap_xmls_dict['test1-revert'] = snap1r_xml

        snap1r0_xml = """<domainsnapshot>
  <name>test1-revert0</name>
  <state>shutoff</state>
  <memory snapshot="no"/>
  <disks>
    <disk name='sda' snapshot='external'>
      <source file='/default-pool/tenv_tnode_tvol.test1-revert0'/>
    </disk>
  </disks>
  <domain type="test">
    <name>tnode</name>
    <devices>
      <disk type='file' device='disk' snapshot='external'>
        <driver name='qemu' type='raw'/>
        <source file='/default-pool/tenv_tnode_tvol.test1-revert0'/>
        <target dev='sda' bus='virtio'/>
      </disk>
    </devices>
    <cpu mode="host-model" />
  </domain>
</domainsnapshot>"""
        self.snap_xmls_dict['test1-revert0'] = snap1r0_xml

        self.node.start()
        self.node.snapshot(name='test1', external=True)
        self.node.snapshot(name='test2', external=True)

        self.snap_create_xml_mock.reset_mock()
        snap1_mock = self.snap_mocks_dict['test1']
        snap1_mock.numChildren.return_value = 1

        snap2_mock = self.snap_mocks_dict['test2']
        snap2_mock.numChildren.return_value = 0

        assert self.node.disk_devices[0].volume.name == 'tvol.test2'

        self.snap_create_xml_mock.reset_mock()

        self.node.revert(name='test1')  # first revert

        self.def_xml_mock.assert_called_once_with("""<domain type="test">
    <name>tnode</name>
    <devices>
      <disk device="disk" snapshot="external" type="file">
        <driver name="qemu" type="raw" />
        <source file="/default-pool/tenv_tnode_tvol.test1" />
        <target bus="virtio" dev="sda" />
      </disk>
    </devices>
    <cpu mode="host-model" />
  </domain>
""")
        assert (self.node.disk_devices[0].volume.name ==
                'tvol.test1-revert')

        pool = self.d.conn.storagePoolLookupByName('default-pool')
        assert len(pool.listAllVolumes()) == 4
        assert len(self.snap_create_xml_mock.mock_calls) == 3
        snapshot1r_xml = (
            '<?xml version="1.0" encoding="utf-8" ?>\n'
            '<domainsnapshot>\n'
            '    <name>test1-revert</name>\n'
            '    <memory snapshot="no" />\n'
            '    <disks>\n'
            '        <disk '
            'file="/default-pool/tenv_tnode_tvol.test1-revert" '
            'name="sda" snapshot="external" />\n'
            '    </disks>\n'
            '</domainsnapshot>')
        xml1 = (
            '<domainsnapshot>\n'
            '  <name>test1</name>\n'
            '  <state>shutoff</state>\n'
            '  <memory snapshot="no" />\n'
            '  <disks>\n'
            '    <disk name="sda" snapshot="external">\n'
            '      <source file="/default-pool/tenv_tnode_tvol.test1" />\n'
            '    </disk>\n'
            '  </disks>\n'
            '  <domain type="test">\n'
            '    <name>tnode</name>\n'
            '    <devices>\n'
            '      <disk device="disk" snapshot="external" type="file">\n'
            '        <driver name="qemu" type="raw" />\n'
            '        <source file="/default-pool/tenv_tnode_tvol.test1" />\n'
            '        <target bus="virtio" dev="sda" />\n'
            '      </disk>\n'
            '    </devices>\n'
            '    <cpu mode="host-model" />\n'
            '  </domain>\n'
            '</domainsnapshot>')
        xml3 = (
            '<domainsnapshot>\n'
            '  <name>test1-revert</name>\n'
            '  <state>shutoff</state>\n'
            '  <memory snapshot="no" />\n'
            '  <disks>\n'
            '    <disk name="sda" snapshot="external">\n'
            '      <source '
            'file="/default-pool/tenv_tnode_tvol.test1-revert" />\n'
            '    </disk>\n'
            '  </disks>\n'
            '  <domain type="test">\n'
            '    <name>tnode</name>\n'
            '    <devices>\n'
            '      <disk device="disk" snapshot="external" type="file">\n'
            '        <driver name="qemu" type="raw" />\n'
            '        <source '
            'file="/default-pool/tenv_tnode_tvol.test1-revert" />\n'
            '        <target bus="virtio" dev="sda" />\n'
            '      </disk>\n'
            '    </devices>\n'
            '    <cpu mode="host-model" />\n'
            '  </domain>\n'
            '</domainsnapshot>')

        self.snap_create_xml_mock.assert_has_calls([
            mock.call(xml1,
                      (libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE |
                       libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT)),
            mock.call(snapshot1r_xml,
                      (libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_DISK_ONLY |
                       libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REUSE_EXT)),
            mock.call(xml3,
                      (libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE |
                       libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT)),
        ])

        snap1r_mock = self.snap_mocks_dict['test1-revert']
        snap1r_mock.numChildren.return_value = 0

        self.node.snapshot(name='test3', external=True)

        self.snap_create_xml_mock.reset_mock()
        self.def_xml_mock.reset_mock()

        with \
                mock.patch('libvirt.virStorageVol.delete') as vol_del_mock,\
                mock.patch('libvirt.virStoragePool.createXML') as\
                pool_crt_mock:
            self.node.revert(name='test1')  # second revert

        assert (self.node.disk_devices[0].volume.name ==
                'tvol.test1-revert')
        vol_del_mock.assert_called_once_with()
        pool_crt_mock.assert_called_once_with("""<volume type='file'>
  <name>tenv_tnode_tvol.test1-revert</name>
  <key>/default-pool/tenv_tnode_tvol.test1-revert</key>
  <source>
  </source>
  <capacity unit='bytes'>512</capacity>
  <allocation unit='bytes'>512</allocation>
  <target>
    <path>/default-pool/tenv_tnode_tvol.test1-revert</path>
    <format type='qcow2'/>
    <permissions>
      <mode>0600</mode>
      <owner>-1</owner>
      <group>-1</group>
    </permissions>
  </target>
  <backingStore>
    <path>/default-pool/tenv_tnode_tvol</path>
    <format type='qcow2'/>
    <permissions>
      <mode>0600</mode>
      <owner>-1</owner>
      <group>-1</group>
    </permissions>
  </backingStore>
</volume>
""")
        self.def_xml_mock.assert_called_once_with("""<domain type="test">
    <name>tnode</name>
    <devices>
      <disk device="disk" snapshot="external" type="file">
        <driver name="qemu" type="raw" />
        <source file="/default-pool/tenv_tnode_tvol.test1-revert" />
        <target bus="virtio" dev="sda" />
      </disk>
    </devices>
    <cpu mode="host-model" />
  </domain>
""")
        xml = (
            '<domainsnapshot>\n'
            '  <name>test1-revert</name>\n'
            '  <state>shutoff</state>\n'
            '  <memory snapshot="no" />\n'
            '  <disks>\n'
            '    <disk name="sda" snapshot="external">\n'
            '      <source '
            'file="/default-pool/tenv_tnode_tvol.test1-revert" />\n'
            '    </disk>\n'
            '  </disks>\n'
            '  <domain type="test">\n'
            '    <name>tnode</name>\n'
            '    <devices>\n'
            '      <disk device="disk" snapshot="external" type="file">\n'
            '        <driver name="qemu" type="raw" />\n'
            '        <source '
            'file="/default-pool/tenv_tnode_tvol.test1-revert" />\n'
            '        <target bus="virtio" dev="sda" />\n'
            '      </disk>\n'
            '    </devices>\n'
            '    <cpu mode="host-model" />\n'
            '  </domain>\n'
            '</domainsnapshot>')
        self.snap_create_xml_mock.assert_has_calls([
            mock.call(xml,
                      (libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE |
                       libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT)),
        ])

        snap1r_mock.numChildren.return_value = 1

        self.snap_create_xml_mock.reset_mock()
        self.def_xml_mock.reset_mock()

        self.node.revert(name='test1')  # third revert

        assert (self.node.disk_devices[0].volume.name ==
                'tvol.test1-revert0')

        xml1 = (
            '<domainsnapshot>\n'
            '  <name>test1</name>\n'
            '  <state>shutoff</state>\n'
            '  <memory snapshot="no" />\n'
            '  <disks>\n'
            '    <disk name="sda" snapshot="external">\n'
            '      <source file="/default-pool/tenv_tnode_tvol.test1" />\n'
            '    </disk>\n'
            '  </disks>\n'
            '  <domain type="test">\n'
            '    <name>tnode</name>\n'
            '    <devices>\n'
            '      <disk device="disk" snapshot="external" type="file">\n'
            '        <driver name="qemu" type="raw" />\n'
            '        <source file="/default-pool/tenv_tnode_tvol.test1" />\n'
            '        <target bus="virtio" dev="sda" />\n'
            '      </disk>\n'
            '    </devices>\n'
            '    <cpu mode="host-model" />\n'
            '  </domain>\n'
            '</domainsnapshot>')

        xml2 = (
            '<?xml version="1.0" encoding="utf-8" ?>\n'
            '<domainsnapshot>\n'
            '    <name>test1-revert0</name>\n'
            '    <memory snapshot="no" />\n'
            '    <disks>\n'
            '        <disk file="/default-pool/tenv_tnode_tvol.test1-revert0"'
            ' name="sda" snapshot="external" />\n'
            '    </disks>\n'
            '</domainsnapshot>')

        xml3 = (
            '<domainsnapshot>\n'
            '  <name>test1-revert0</name>\n'
            '  <state>shutoff</state>\n'
            '  <memory snapshot="no" />\n'
            '  <disks>\n'
            '    <disk name="sda" snapshot="external">\n'
            '      <source file="/default-pool/tenv_tnode_tvol.test1-revert0" '
            '/>\n'
            '    </disk>\n'
            '  </disks>\n'
            '  <domain type="test">\n'
            '    <name>tnode</name>\n'
            '    <devices>\n'
            '      <disk device="disk" snapshot="external" type="file">\n'
            '        <driver name="qemu" type="raw" />\n'
            '        <source '
            'file="/default-pool/tenv_tnode_tvol.test1-revert0" />\n'
            '        <target bus="virtio" dev="sda" />\n'
            '      </disk>\n'
            '    </devices>\n'
            '    <cpu mode="host-model" />\n'
            '  </domain>\n'
            '</domainsnapshot>')

        self.snap_create_xml_mock.assert_has_calls([
            mock.call(xml1,
                      (libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE |
                       libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT)),
            mock.call(xml2,
                      (libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_DISK_ONLY |
                       libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REUSE_EXT)),
            mock.call(xml3,
                      (libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE |
                       libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT)),
        ])
