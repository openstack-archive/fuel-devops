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

import libvirt
import mock
import pytest
from unittest import TestCase
import xml.etree.ElementTree as ET

from devops.driver.libvirt.libvirt_driver import Driver
from devops.tests import factories


@pytest.mark.xfail(reason='to rewrite')
class TestLibvirtDriver(TestCase):

    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.'
        'node_snapshot_exists')
    @mock.patch('devops.driver.libvirt.libvirt_driver.libvirt.open')
    def test_node_create_snapshot_if_exists(self, mock_conn,
                                            mock_snapshot_exists):
        mock_snapshot_exists.return_value = True
        mock_conn.return_value.lookupByUUIDString.return_value = mock.Mock()

        dd = Driver()
        dd.node_create_snapshot('node')

        self.assertEqual(mock_conn.lookupByUUIDString.called, False)

    @mock.patch(
        'devops.driver.libvirt.libvirt_xml_builder.LibvirtXMLBuilder.'
        'build_snapshot_xml')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.'
        'node_snapshot_exists')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.'
        'node_get_snapshots')
    @mock.patch('devops.driver.libvirt.libvirt_driver.libvirt.open')
    def test_node_create_snapshot_internal_if_external_exists(
            self, mock_conn, mock_get_snapshots,
            mock_snapshot_exists, mock_snapshot_xml):
        mock_snapshot_exists.return_value = False
        mock_get_snapshots.return_value = [mock.Mock(get_type='external')]
        mock_conn.return_value.lookupByUUIDString.return_value = mock.Mock()
        node = mock.Mock(uuid='test_node')

        dd = Driver()
        dd.node_create_snapshot(node)

        self.assertEqual(mock_snapshot_xml.called, False)

    @mock.patch(
        'devops.driver.libvirt.libvirt_xml_builder.LibvirtXMLBuilder.'
        'build_snapshot_xml')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.'
        'node_snapshot_exists')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.'
        'node_get_snapshots')
    @mock.patch('devops.driver.libvirt.libvirt_driver.libvirt.open')
    def test_node_create_snapshot_external_if_internal_exists(
            self, mock_conn, mock_get_snapshots,
            mock_snapshot_exists, mock_snapshot_xml):
        mock_snapshot_exists.return_value = False
        mock_get_snapshots.return_value = [mock.Mock(get_type='internal')]
        mock_conn.return_value.lookupByUUIDString.return_value = mock.Mock()
        node = mock.Mock(uuid='test_node')

        dd = Driver()
        dd.node_create_snapshot(node, external=True)

        self.assertEqual(mock_snapshot_xml.called, False)

    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.settings.SNAPSHOTS_EXTERNAL_DIR',
        '/path/snap')
    @mock.patch(
        'devops.driver.libvirt.libvirt_xml_builder.LibvirtXMLBuilder.'
        'build_snapshot_xml')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.'
        'node_snapshot_exists')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.node_get_snapshots')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.'
        'node_set_snapshot_current')
    @mock.patch('devops.driver.libvirt.libvirt_driver.os')
    @mock.patch('devops.driver.libvirt.libvirt_driver.libvirt.open')
    def test_node_create_snapshot_external(
            self, mock_conn, mock_os, mock_set_snapshot_current,
            mock_get_snapshots, mock_snapshot_exists, mock_snapshot_xml):
        mock_snapshot_exists.return_value = False
        mock_get_snapshots.return_value = [mock.Mock(get_type='external')]
        domain = mock.Mock()
        domain.isActive.return_value = True
        domain.snapshotCreateXML.return_value = True
        mock_conn.return_value.lookupByUUIDString.return_value = domain
        node = mock.Mock(uuid='test_node')
        mock_os.path.exists.return_value = False

        snapshot_name = factories.fuzzy_string()
        description = factories.fuzzy_string('description_')
        xml_fuzzy = factories.fuzzy_string()
        xml = '<{0}/>'.format(xml_fuzzy)
        mock_snapshot_xml.return_value = xml
        disk_only = False
        external = True

        dd = Driver()
        dd.node_create_snapshot(node, name=snapshot_name, disk_only=disk_only,
                                description=description, external=external)

        mock_snapshot_xml.assert_called_with(snapshot_name, description, node,
                                             disk_only, external, '/path/snap')
        self.assertEqual(mock_os.makedirs.called, True)
        self.assertEqual(domain.snapshotCreateXML.called, True)
        domain.snapshotCreateXML.assert_called_with(
            xml, libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REUSE_EXT)
        mock_set_snapshot_current.assert_called_with(node, snapshot_name)

    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.settings.SNAPSHOTS_EXTERNAL_DIR',
        '/path/snap')
    @mock.patch(
        'devops.driver.libvirt.libvirt_xml_builder.LibvirtXMLBuilder.'
        'build_snapshot_xml')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.'
        'node_snapshot_exists')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.node_get_snapshots')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.'
        'node_set_snapshot_current')
    @mock.patch('devops.driver.libvirt.libvirt_driver.os')
    @mock.patch('devops.driver.libvirt.libvirt_driver.libvirt.open')
    def test_node_create_snapshot_external_domain_not_active(
            self, mock_conn, mock_os, mock_set_snapshot_current,
            mock_get_snapshots, mock_snapshot_exists, mock_snapshot_xml):
        mock_snapshot_exists.return_value = False
        mock_get_snapshots.return_value = [mock.Mock(get_type='external')]
        node = mock.Mock(uuid='test_node')
        mock_os.path.exists.return_value = False

        domain = mock.Mock()
        domain.isActive.return_value = False
        domain.snapshotCreateXML.return_value = True
        mock_conn.return_value.lookupByUUIDString.return_value = domain

        snapshot_name = factories.fuzzy_string()
        description = factories.fuzzy_string('description_')
        xml_fuzzy = factories.fuzzy_string()
        xml = '<{0}/>'.format(xml_fuzzy)
        mock_snapshot_xml.return_value = xml
        disk_only = False
        external = True

        dd = Driver()
        dd.node_create_snapshot(node, name=snapshot_name, disk_only=disk_only,
                                description=description, external=external)

        mock_snapshot_xml.assert_called_with(snapshot_name, description, node,
                                             disk_only, external, '/path/snap')
        self.assertEqual(mock_os.makedirs.called, True)
        self.assertEqual(domain.snapshotCreateXML.called, True)
        domain.snapshotCreateXML.assert_called_with(
            xml, libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_DISK_ONLY |
            libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REUSE_EXT)
        mock_set_snapshot_current.assert_called_with(node, snapshot_name)

    @mock.patch('devops.driver.libvirt.libvirt_driver.libvirt.open')
    def test_node_set_snapshot_current(self, mock_conn):
        xml_fuzzy = factories.fuzzy_string()
        xml = '<{0}/>'.format(xml_fuzzy)
        snapshot = mock.Mock()
        snapshot.getXMLDesc.return_value = xml
        domain = mock.Mock()
        domain.isActive.return_value = False
        domain.snapshotCreateXML.return_value = True
        domain.snapshotCurrent.return_value = snapshot
        domain.snapshotLookupByName.return_value = snapshot
        mock_conn.return_value.lookupByUUIDString.return_value = domain
        node = mock.Mock(uuid='test_node')
        snapshot_name = factories.fuzzy_string()

        dd = Driver()
        dd.node_set_snapshot_current(node, snapshot_name)

        domain.snapshotCreateXML.assert_called_with(
            xml, libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE |
            libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT)

    @mock.patch('devops.driver.libvirt.libvirt_driver.libvirt.open')
    @mock.patch('devops.driver.libvirt.libvirt_driver.os')
    def test_delete_snaphost_files(self, mock_os, mock_conn):
        mock_os.path.isfile.return_value = True
        mock_os.remove.return_value = True

        memory_file = factories.fuzzy_string('/path/to/')
        snapshot_xml = '''<domainsnapshot>
  <memory file="{0}" snapshot="external"/>
</domainsnapshot>'''.format(memory_file)
        snapshot = mock.Mock()
        snapshot.getXMLDesc.return_value = snapshot_xml

        dd = Driver()
        dd._delete_snapshot_files(snapshot)

        mock_os.remove.assert_called_with(memory_file)

    @mock.patch('devops.driver.libvirt.libvirt_driver.libvirt.open')
    @mock.patch('devops.driver.libvirt.libvirt_driver.os')
    def test_delete_snaphost_files_internal(self, mock_os, mock_conn):
        mock_os.path.isfile.return_value = True
        mock_os.remove.return_value = True

        snapshot_xml = '''<domainsnapshot>
  <memory snapshot="internal"/>
</domainsnapshot>'''
        snapshot = mock.Mock()
        snapshot.getXMLDesc.return_value = snapshot_xml

        dd = Driver()
        dd._delete_snapshot_files(snapshot)

        self.assertEqual(mock_os.remove.called, False)

    @mock.patch('devops.driver.libvirt.libvirt_driver.libvirt.open')
    def test_node_delete_snaphost_internal(self, mock_conn):
        snapshot_xml = '''<domainsnapshot>
  <memory snapshot="internal"/>
</domainsnapshot>'''
        snapshot = mock.Mock()
        snapshot.numChildren.return_value = 0
        snapshot.getXMLDesc.return_value = snapshot_xml
        snapshot.delete.return_value = True
        domain = mock.Mock()
        domain.isActive.return_value = True
        domain.snapshotCreateXML.return_value = True
        domain.snapshotCurrent.return_value = snapshot
        domain.snapshotLookupByName.return_value = snapshot
        mock_conn.return_value.lookupByUUIDString.return_value = domain
        node = mock.Mock(uuid='test_node')

        dd = Driver()
        dd.node_delete_snapshot(node, 'snapname')

        snapshot.delete.assert_called_with(0)
        self.assertEqual(snapshot.numChildren.called, False)

    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.'
        '_delete_snapshot_files')
    @mock.patch('devops.driver.libvirt.libvirt_driver.libvirt.open')
    def test_node_delete_snaphost_external_has_children(
            self, mock_conn, mock_delete_snapshot_files):
        snapshot_xml = '''<domainsnapshot>
  <memory snapshot="external"/>
</domainsnapshot>'''
        snapshot = mock.Mock()
        snapshot.numChildren.return_value = 1
        snapshot.getXMLDesc.return_value = snapshot_xml
        snapshot.delete.return_value = True
        domain = mock.Mock()
        domain.isActive.return_value = False
        domain.snapshotCreateXML.return_value = True
        domain.snapshotCurrent.return_value = snapshot
        domain.snapshotLookupByName.return_value = snapshot
        mock_conn.return_value.lookupByUUIDString.return_value = domain
        node = mock.Mock(uuid='test_node')

        dd = Driver()
        dd.node_delete_snapshot(node, 'snapname')

        self.assertEqual(snapshot.numChildren.called, True)
        self.assertEqual(domain.isActive.called, False)
        self.assertEqual(snapshot.delete.called, False)

    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.'
        '_delete_snapshot_files')
    @mock.patch('devops.driver.libvirt.libvirt_driver.libvirt.open')
    def test_node_delete_snaphost_external(self, mock_conn,
                                           mock_delete_snapshot_files):
        domain_xml = '''<domain>
    <name>{0}</name>
    <devices>
      <disk type='file' device='disk' snapshot='external'>
        <driver name='qemu' type='raw'/>
        <source file='{1}'/>
        <target dev='vda' bus='virtio'/>
      </disk>
      <disk type='file' device='disk' snapshot='external'>
        <driver name='qemu' type='raw'/>
        <source file='{2}'/>
        <target dev='vdb' bus='virtio'/>
      </disk>
    </devices>
  </domain>'''.format(factories.fuzzy_string('name_'),
                      factories.fuzzy_string('/path/to/'),
                      factories.fuzzy_string('/path/to/'))
        snapshot_xml = '''<domainsnapshot>
  <memory snapshot="external"/>
  <disks/>
  {0}
</domainsnapshot>'''.format(domain_xml)
        snapshot = mock.Mock()
        snapshot.numChildren.return_value = 0
        snapshot.getXMLDesc.return_value = snapshot_xml
        snapshot.delete.return_value = True
        domain = mock.Mock()
        domain.isActive.return_value = True
        domain.snapshotCreateXML.return_value = True
        domain.snapshotCurrent.return_value = snapshot
        domain.snapshotLookupByName.return_value = snapshot
        mock_conn.return_value.lookupByUUIDString.return_value = domain
        mock_conn.return_value.defineXML.return_value = True
        node = mock.Mock(uuid='test_node')

        dd = Driver()
        dd.node_delete_snapshot(node, 'snapname')

        self.assertEqual(domain.destroy.called, True)
        mock_delete_snapshot_files.assert_called_with(snapshot)
        snapshot.delete.assert_called_with(2)
        mock_conn().defineXML.assert_called_with(
            '{0}\n'.format(ET.tostring(ET.fromstring(domain_xml))))

    @mock.patch('devops.driver.libvirt.libvirt_driver.libvirt.open')
    def test_node_revert_snapshot_recreate_disks_has_children(self, mock_conn):
        snapshot = mock.Mock()
        snapshot.children_num = 1
        domain = mock.Mock()
        domain.isActive.return_value = True
        domain.snapshotCreateXML.return_value = True
        domain.snapshotCurrent.return_value = snapshot
        domain.snapshotLookupByName.return_value = snapshot
        mock_conn.return_value.lookupByUUIDString.return_value = domain
        mock_conn.return_value.storageVolLookupByKey.return_value = mock.Mock()
        node = mock.Mock(uuid='test_node')

        dd = Driver()
        dd.node_revert_snapshot_recreate_disks(node, 'snapname')

        self.assertEqual(mock_conn.storageVolLookupByKey.called, False)

    @mock.patch('devops.driver.libvirt.libvirt_driver.libvirt.open')
    def test_node_revert_snapshot_recreate_disks(self, mock_conn):
        disk1_file = factories.fuzzy_string('/var/lib/libvirt/images/')
        disk2_file = factories.fuzzy_string('/var/lib/libvirt/images/')
        snapshot_xml = '''<domainsnapshot>
  <memory snapshot="no"/>
  <disks>
    <disk name='vda' snapshot='external'>
      <source file='{0}'/>
    </disk>
    <disk name='vdb' snapshot='external'>
      <source file='{1}'/>
    </disk>
  </disks>
</domainsnapshot>'''.format(disk1_file, disk2_file)
        snapshot = mock.Mock()
        snapshot.getXMLDesc.return_value = snapshot_xml
        snapshot.numChildren.return_value = 0

        domain = mock.Mock()
        domain.isActive.return_value = True
        domain.snapshotCreateXML.return_value = True
        domain.snapshotCurrent.return_value = False
        domain.snapshotLookupByName.return_value = snapshot
        mock_conn.return_value.lookupByUUIDString.return_value = domain

        pool = mock.Mock()
        pool.createXML.return_value = mock.Mock()

        def define_volume(*args):
            volume_xml = '<{0}/>'.format(args[0])
            volume = mock.Mock()
            volume.XMLDesc.return_value = volume_xml
            volume.storagePoolLookupByVolume.return_value = pool
            volume.detele.return_value = True
            return volume

        volume1 = define_volume(disk1_file)
        volume2 = define_volume(disk2_file)

        def return_volume(*args):
            if args[0] == disk1_file:
                return volume1
            elif args[0] == disk2_file:
                return volume2

        mock_conn.return_value.storageVolLookupByKey.side_effect = \
            return_volume
        node = mock.Mock(uuid='test_node')

        dd = Driver()
        dd.node_revert_snapshot_recreate_disks(node, 'snapname')

        self.assertEqual(volume1.delete.called, True)
        self.assertEqual(volume2.delete.called, True)
        mock_conn().storageVolLookupByKey.assert_has_calls(
            [mock.call(disk1_file), mock.call(disk2_file)],
            any_order=True)
        pool.createXML.assert_has_calls(
            [mock.call(volume1.XMLDesc()),
                mock.call(volume2.XMLDesc())],
            any_order=True)

    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.node_active')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.node_destroy')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.'
        'node_set_snapshot_current')
    @mock.patch('devops.driver.libvirt.libvirt_driver.libvirt.open')
    def test_node_revert_snapshot_has_children(
            self, mock_conn, mock_set_snapshot_current,
            mock_node_active, mock_node_destroy):
        snapshot_name = factories.fuzzy_string('name_')
        domain_name = factories.fuzzy_string('domain_')
        memory_snapshot_path = factories.fuzzy_string('/path/to/')
        disk1_path = factories.fuzzy_string('/path/to/')
        disk2_path = factories.fuzzy_string('/path/to/')
        snapshot1_path = factories.fuzzy_string('/path/to/')
        snapshot2_path = factories.fuzzy_string('/path/to/')
        domain_xml_tmpl = '''  <domain>
    <name>{0}</name>
    <devices>
      <disk type='file' device='disk' snapshot='external'>
        <driver name='qemu' type='raw'/>
        <source file='{1}'/>
        <target dev='vda' bus='virtio'/>
      </disk>
      <disk type='file' device='disk' snapshot='external'>
        <driver name='qemu' type='raw'/>
        <source file='{2}'/>
        <target dev='vdb' bus='virtio'/>
      </disk>
    </devices>
  </domain>'''
        domain_xml = domain_xml_tmpl.format(
            domain_name, disk1_path, disk2_path)
        snapshot_xml = '''<domainsnapshot>
  <name>{0}</name>
  <description>Snapshot of OS install and updates</description>
  <state>running</state>
  <creationTime>1270477159</creationTime>
  <parent>
    <name>bare-os-install</name>
  </parent>
  <memory file='{1}' snapshot='external'/>
  <disks>
    <disk name='vda' snapshot='external'>
      <driver type='qcow2'/>
      <source file='{2}'/>
    </disk>
    <disk name='vdb' snapshot='external'>
      <driver type='qcow2'/>
      <source file='{3}'/>
    </disk>
  </disks>
  {4}
</domainsnapshot>'''.format(snapshot_name, memory_snapshot_path,
                            snapshot1_path, snapshot2_path, domain_xml)
        snapshot = mock.Mock()
        snapshot.numChildren.return_value = 1
        snapshot.getXMLDesc.return_value = snapshot_xml
        domain = mock.Mock()
        domain.isActive.return_value = True
        domain.snapshotCreateXML.return_value = True
        domain.snapshotCurrent.return_value = snapshot
        domain.snapshotLookupByName.return_value = snapshot
        mock_conn.return_value.lookupByUUIDString.return_value = domain
        node = mock.Mock(uuid='test_node')
        mock_node_active.return_value = True

        dd = Driver()
        dd.node_revert_snapshot(node, snapshot_name)

        mock_node_destroy.assert_called_with(node)
        mock_conn().restoreFlags.assert_called_with(
            memory_snapshot_path,
            dxml='{0}\n'.format(ET.tostring(ET.fromstring(domain_xml))),
            flags=libvirt.VIR_DOMAIN_SAVE_PAUSED)
        mock_set_snapshot_current.assert_called_with(node, snapshot_name)

    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.'
        'node_set_snapshot_current')
    @mock.patch('devops.driver.libvirt.libvirt_driver.libvirt.open')
    def test_node_revert_snapshot_internal(self, mock_conn,
                                           mock_set_snapshot_current):
        snapshot_xml = '''<domainsnapshot>
  <state>running</state>
  <memory snapshot="internal"/>
  <disks/>
</domainsnapshot>'''
        snapshot = mock.Mock()
        snapshot.getXMLDesc.return_value = snapshot_xml
        domain = mock.Mock()
        domain.snapshotCreateXML.return_value = True
        domain.snapshotCurrent.return_value = snapshot
        domain.snapshotLookupByName.return_value = snapshot
        mock_conn.return_value.lookupByUUIDString.return_value = domain
        node = mock.Mock(uuid='test_node')

        dd = Driver()
        dd.node_revert_snapshot(node, 'snapname')

        self.assertEqual(mock_set_snapshot_current.called, False)
        domain.revertToSnapshot.assert_called_with(snapshot, 0)

    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.node_destroy')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.node_active')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.'
        'node_set_snapshot_current')
    @mock.patch('devops.driver.libvirt.libvirt_driver.libvirt.open')
    def test_node_revert_snapshot_shutoff(
            self, mock_conn, mock_set_snapshot_current,
            mock_node_active, mock_node_destroy):
        snapshot_name = factories.fuzzy_string('name_')
        domain_name = factories.fuzzy_string('domain_')
        disk1_path = factories.fuzzy_string('/path/to/')
        snapshot1_path = factories.fuzzy_string('/path/to/')
        domain_xml_tmpl = '''  <domain>
    <name>{0}</name>
    <devices>
      <disk type='file' device='disk' snapshot='external'>
        <driver name='qemu' type='raw'/>
        <source file='{1}'/>
        <target dev='vda' bus='virtio'/>
      </disk>
    </devices>
  </domain>'''
        domain_xml = domain_xml_tmpl.format(domain_name, disk1_path)
        snapshot_xml = '''<domainsnapshot>
  <name>{0}</name>
  <state>shutoff</state>
  <memory snapshot='no'/>
  <disks>
    <disk name='vda' snapshot='external'>
      <driver type='qcow2'/>
      <source file='{1}'/>
    </disk>
  </disks>
  {2}
</domainsnapshot>'''.format(snapshot_name, snapshot1_path, domain_xml)
        snapshot = mock.Mock()
        snapshot.numChildren.return_value = 0
        snapshot.getXMLDesc.return_value = snapshot_xml
        domain = mock.Mock()
        domain.snapshotCreateXML.return_value = True
        domain.snapshotCurrent.return_value = snapshot
        domain.snapshotLookupByName.return_value = snapshot
        mock_conn.return_value.lookupByUUIDString.return_value = domain
        node = mock.Mock(uuid='test_node')
        mock_node_active.return_value = False

        dd = Driver()
        dd.node_revert_snapshot(node, snapshot_name)

        domain_xml_expected = domain_xml_tmpl.format(domain_name,
                                                     snapshot1_path)

        self.assertEqual(mock_node_destroy.called, False)
        mock_conn().defineXML.assert_called_with(
            '{0}\n'.format(ET.tostring(ET.fromstring(domain_xml_expected))))
        mock_set_snapshot_current.assert_called_with(node, snapshot_name)

    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.node_destroy')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.node_active')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.Driver.'
        'node_set_snapshot_current')
    @mock.patch('devops.driver.libvirt.libvirt_driver.libvirt.open')
    def test_node_revert_snapshot(self, mock_conn,
                                  mock_set_snapshot_current, mock_node_active,
                                  mock_node_destroy):
        snapshot_name = factories.fuzzy_string('name_')
        domain_name = factories.fuzzy_string('domain_')
        memory_snapshot_path = factories.fuzzy_string('/path/to/')
        disk1_path = factories.fuzzy_string('/path/to/')
        disk2_path = factories.fuzzy_string('/path/to/')
        snapshot1_path = factories.fuzzy_string('/path/to/')
        snapshot2_path = factories.fuzzy_string('/path/to/')
        domain_xml_tmpl = '''  <domain>
    <name>{0}</name>
    <devices>
      <disk type='file' device='disk' snapshot='external'>
        <driver name='qemu' type='raw'/>
        <source file='{1}'/>
        <target dev='vda' bus='virtio'/>
      </disk>
      <disk type='file' device='disk' snapshot='external'>
        <driver name='qemu' type='raw'/>
        <source file='{2}'/>
        <target dev='vdb' bus='virtio'/>
      </disk>
    </devices>
  </domain>'''
        domain_xml = domain_xml_tmpl.format(domain_name,
                                            disk1_path, disk2_path)
        snapshot_xml = '''<domainsnapshot>
  <name>{0}</name>
  <state>running</state>
  <memory file='{1}' snapshot='external'/>
  <disks>
    <disk name='vda' snapshot='external'>
      <driver type='qcow2'/>
      <source file='{2}'/>
    </disk>
    <disk name='vdb' snapshot='external'>
      <driver type='qcow2'/>
      <source file='{3}'/>
    </disk>
  </disks>
  {4}
</domainsnapshot>'''.format(snapshot_name, memory_snapshot_path,
                            snapshot1_path, snapshot2_path, domain_xml)
        snapshot = mock.Mock()
        snapshot.numChildren.return_value = 0
        snapshot.getXMLDesc.return_value = snapshot_xml
        domain = mock.Mock()
        domain.snapshotCreateXML.return_value = True
        domain.snapshotCurrent.return_value = snapshot
        domain.snapshotLookupByName.return_value = snapshot
        mock_conn.return_value.lookupByUUIDString.return_value = domain
        node = mock.Mock(uuid='test_node')
        mock_node_active.return_value = True

        dd = Driver()
        dd.node_revert_snapshot(node, snapshot_name)

        domain_xml_expected = domain_xml_tmpl.format(
            domain_name, snapshot1_path, snapshot2_path)

        mock_node_destroy.assert_called_with(node)
        mock_conn().restoreFlags.assert_called_with(
            memory_snapshot_path,
            dxml='{0}\n'.format(ET.tostring(ET.fromstring(
                domain_xml_expected))),
            flags=libvirt.VIR_DOMAIN_SAVE_PAUSED)
        mock_set_snapshot_current.assert_called_with(node, snapshot_name)
