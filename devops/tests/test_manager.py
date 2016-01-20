#    Copyright 2013 - 2014 Mirantis, Inc.
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
import pytest

from devops.models import Address
from devops.models import AddressPool
from devops.models import DiskDevice
from devops.models import Environment
from devops.models import Interface
from devops.models import L2NetworkDevice
from devops.models import Node
from devops.models import Volume
from devops.tests import factories


class TestManager(TestCase):

    def test_network_iterator(self):
        environment = Environment.create('test_env')
        node = Node.objects.create(
            group=None,
            name='test_node',
            role='default',
        )
        address_pool = AddressPool.address_pool_create(
            environment=environment, name='internal', ip_network='10.1.0.0/24')
        l2_net_dev = L2NetworkDevice.objects.create(
            group=None, address_pool=address_pool, name='test_l2_dev')
        interface = Interface.interface_create(l2_network_device=l2_net_dev,
                                               node=node, label='eth0')
        assert str(address_pool.next_ip()) == '10.1.0.3'
        Address.objects.create(ip_address=str('10.1.0.3'),
                               interface=interface)
        assert str(address_pool.next_ip()) == '10.1.0.4'
        Address.objects.create(ip_address=str('10.1.0.4'),
                               interface=interface)
        assert str(address_pool.next_ip()) == '10.1.0.5'

    def test_network_model(self):
        environment = Environment.create('test_env')
        node = Node.objects.create(
            group=None,
            name='test_node',
            role='default',
        )
        address_pool = AddressPool.address_pool_create(
            environment=environment, name='internal', ip_network='10.1.0.0/24')
        l2_net_dev = L2NetworkDevice.objects.create(
            group=None, address_pool=address_pool, name='test_l2_dev')

        interface1 = Interface.interface_create(l2_network_device=l2_net_dev,
                                                node=node, label='eth0')

        assert interface1.model == 'virtio'
        interface2 = Interface.interface_create(l2_network_device=l2_net_dev,
                                                node=node, label='eth0',
                                                model='e1000')
        assert interface2.model == 'e1000'

    def test_network_pool(self):
        environment = Environment.create('test_env2')
        self.assertEqual('10.0.0.0/24', str(AddressPool.address_pool_create(
            environment=environment, name='internal', pool=None).ip_network))
        self.assertEqual('10.0.1.0/24', str(AddressPool.address_pool_create(
            environment=environment, name='external', pool=None).ip_network))
        self.assertEqual('10.0.2.0/24', str(AddressPool.address_pool_create(
            environment=environment, name='private', pool=None).ip_network))

        environment = Environment.create('test_env3')
        self.assertEqual('10.0.3.0/24', str(AddressPool.address_pool_create(
            environment=environment, name='internal', pool=None).ip_network))
        self.assertEqual('10.0.4.0/24', str(AddressPool.address_pool_create(
            environment=environment, name='external', pool=None).ip_network))
        self.assertEqual('10.0.5.0/24', str(AddressPool.address_pool_create(
            environment=environment, name='private', pool=None).ip_network))

    def test_node_creation(self):
        environment = Environment.create('test_env3')
        address_pool = AddressPool.address_pool_create(
            environment=environment, name='internal', ip_network='10.1.0.0/24')
        l2_net_dev = L2NetworkDevice.objects.create(
            group=None, address_pool=address_pool, name='test_l2_dev')

        node = Node.objects.create(
            group=None,
            name='test_node',
            role='default',
        )
        Interface.interface_create(l2_network_device=l2_net_dev,
                                   node=node, label='eth0')
        environment.define()

    @pytest.mark.xfail(reason='to rewrite')
    def test_create_volume(self):
        environment = Environment.create('test_env3')
        volume = Volume.volume_get_predefined(
            '/var/lib/libvirt/images/disk-135824657433.qcow2')
        v3 = Volume.volume_create_child(
            'test_vp89', backing_store=volume, environment=environment)
        v3.define()

    # @pytest.mark.xfail(reason='to rewrite')
    # def test_create_node3(self):
    #     environment = Environment.create('test_env3')
    #     internal = Network.network_create(
    #         environment=environment, name='internal', pool=None)
    #     external = Network.network_create(
    #         environment=environment, name='external', pool=None)
    #     private = Network.network_create(
    #         environment=environment, name='private', pool=None)
    #     node = Node.node_create(name='test_node', environment=environment)
    #     Interface.interface_create(node=node, network=internal)
    #     Interface.interface_create(node=node, network=external)
    #     Interface.interface_create(node=node, network=private)
    #     volume = Volume.volume_get_predefined(
    #         '/var/lib/libvirt/images/disk-135824657433.qcow2')
    #     v3 = Volume.volume_create_child('test_vp892',
    #                                     backing_store=volume,
    #                                     environment=environment)
    #     v4 = Volume.volume_create_child('test_vp891',
    #                                     backing_store=volume,
    #                                     environment=environment)
    #     DiskDevice.node_attach_volume(node=node, volume=v3)
    #     DiskDevice.node_attach_volume(node, v4)
    #     environment.define()

    @pytest.mark.xfail(reason='to rewrite')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'node_create_snapshot')
    @mock.patch('devops.models.node.Node.has_snapshot')
    def test_snapshot_with_existing_name(self, mock_has_snapshot,
                                         mock_node_create_snapshot):
        mock_has_snapshot.return_value = True

        environment = Environment.create('test_env_extsnap')
        node = Node.node_create(name='test_node', environment=environment)
        environment.define()

        node.snapshot(name='test_name')
        self.assertEqual(mock_node_create_snapshot.called, False)

    @pytest.mark.xfail(reason='to rewrite')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'node_create_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'node_delete_snapshot')
    @mock.patch('devops.models.node.Node.has_snapshot')
    def test_snapshot_with_existing_name_force_delete(
            self, mock_has_snapshot, mock_delete_snapshot,
            mock_create_snapshot):
        mock_has_snapshot.return_value = True

        environment = Environment.create('test_env_extsnap')
        node = Node.node_create(name='test_node', environment=environment)
        environment.define()

        snap_name = factories.fuzzy_string('snap_')
        snap_description = factories.fuzzy_string('description_')

        node.snapshot(name=snap_name, force=True,
                      description=snap_description, disk_only=True)

        self.assertEqual(mock_delete_snapshot.called, True)
        mock_delete_snapshot.assert_called_with(node=node, name=snap_name)
        mock_create_snapshot.assert_called_with(
            node=node, name=snap_name, description=snap_description,
            disk_only=True, external=False)

    @pytest.mark.xfail(reason='to rewrite')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'node_create_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'get_libvirt_version')
    @mock.patch('devops.models.node.Node.has_snapshot')
    def test_external_snapshot_incorrect_libvirt_version(
            self, mock_has_snapshot, mock_libvirt_version,
            mock_create_snapshot):
        mock_has_snapshot.return_value = False
        mock_libvirt_version.return_value = 1002009

        environment = Environment.create('test_env_extsnap')
        node = Node.node_create(name='test_node', environment=environment)
        environment.define()

        node.snapshot(name='test_name', external=True)

        self.assertEqual(mock_create_snapshot.called, False)

    @pytest.mark.xfail(reason='to rewrite')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'node_create_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'get_libvirt_version')
    @mock.patch('devops.models.node.Node.snapshot_create_volume')
    @mock.patch('devops.models.node.Node.has_snapshot')
    def test_external_snapshot(
            self, mock_has_snapshot, mock_create_volume,
            mock_libvirt_version, mock_create_snapshot):
        mock_has_snapshot.return_value = False
        mock_libvirt_version.return_value = 1002012

        environment = Environment.create('test_env_extsnap')
        node = Node.node_create(name='test_node', environment=environment)
        vol_volume_name = factories.fuzzy_string()
        vol = Volume.volume_create(vol_volume_name,
                                   capacity=1000000000,
                                   format='qcow2',
                                   environment=environment)
        DiskDevice.node_attach_volume(node=node, volume=vol)
        environment.define()

        snap_name = factories.fuzzy_string('snap_')
        snap_description = factories.fuzzy_string('description_')

        node.snapshot(name=snap_name, description=snap_description,
                      external=True)

        mock_create_volume.assert_called_with(snap_name)
        mock_create_snapshot.assert_called_with(
            node=node, name=snap_name, description=snap_description,
            disk_only=False, external=True)

    @pytest.mark.xfail(reason='to rewrite')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'node_delete_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'node_get_snapshot')
    @mock.patch('devops.models.node.Node.has_snapshot')
    def test_external_snapshot_with_children_erase(
            self, mock_has_snapshot, mock_get_snapshot,
            mock_delete_snapshot):
        mock_has_snapshot.return_value = True
        mock_get_snapshot.return_value = mock.Mock(get_type='external',
                                                   children_num=1)

        environment = Environment.create('test_env_extsnap')
        node = Node.node_create(name='test_node', environment=environment)
        environment.define()

        snap_name = factories.fuzzy_string('snap_')
        node.erase_snapshot(snap_name)

        self.assertEqual(mock_delete_snapshot.called, False)
        mock_get_snapshot.assert_called_with(node, snap_name)

    @pytest.mark.xfail(reason='to rewrite')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'node_create_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.node_get_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'node_delete_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'get_libvirt_version')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.volume_define')
    @mock.patch('devops.models.node.Node.has_snapshot')
    def test_external_snapshot_erase(
            self, mock_has_snapshot, mock_volume_define,
            mock_libvirt_version, mock_delete_snapshot,
            mock_get_snapshot, mock_create_snapshot):
        mock_has_snapshot.return_value = False
        mock_libvirt_version.return_value = 1002012
        mock_get_snapshot.return_value = mock.Mock(get_type='external',
                                                   children_num=0)

        environment = Environment.create('test_env_extsnap')
        node = Node.node_create(name='test_node', environment=environment)
        vol_volume_name = factories.fuzzy_string()
        vol = Volume.volume_create(vol_volume_name,
                                   capacity=1000000000,
                                   format='qcow2',
                                   environment=environment)
        DiskDevice.node_attach_volume(node=node, volume=vol)
        environment.define()

        snap_name = factories.fuzzy_string('snap_')
        snap_description = factories.fuzzy_string('description_')

        node.snapshot(name=snap_name, description=snap_description,
                      external=True)

        mock_has_snapshot.return_value = True

        node.erase_snapshot(snap_name)

        mock_delete_snapshot.assert_called_with(node=node, name=snap_name)
        self.assertEqual(node.disk_devices[0].volume, vol)

    @pytest.mark.xfail(reason='to rewrite')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'node_create_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.node_get_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'get_libvirt_version')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.volume_define')
    @mock.patch('devops.models.node.Node.has_snapshot')
    def test_update_disks_from_snapshot_no_children(
            self, mock_has_snapshot, mock_volume_define,
            mock_libvirt_version,
            mock_get_snapshot, mock_create_snapshot):
        mock_has_snapshot.return_value = False
        mock_libvirt_version.return_value = 1002012
        volume_path_template = '/var/lib/libvirt/images/{0}'

        environment = Environment.create('test_env_extsnap')
        node = Node.node_create(name='test_node', environment=environment)
        vol_volume_name = factories.fuzzy_string()
        vol = Volume.volume_create(vol_volume_name,
                                   capacity=1000000000,
                                   format='qcow2',
                                   environment=environment)
        vol.uuid = volume_path_template.format(vol_volume_name)
        DiskDevice.node_attach_volume(node=node, volume=vol)
        environment.define()

        snap_name = factories.fuzzy_string('snap_')
        snap_description = factories.fuzzy_string('description_')
        snapshot_volume_name = '{0}.{1}'.format(vol_volume_name,
                                                snap_name)
        mock_get_snapshot.return_value = mock.Mock(
            get_type='external', children_num=0,
            disks={'sda': volume_path_template.format(snap_name)})

        node.snapshot(name=snap_name, description=snap_description,
                      external=True)
        vol1 = environment.get_volume(name=snapshot_volume_name)
        vol1.uuid = volume_path_template.format(snap_name)
        vol1.save()

        node._update_disks_from_snapshot(snap_name)
        self.assertEqual(node.disk_devices[0].volume, vol1)

    @pytest.mark.xfail(reason='to rewrite')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'node_create_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.node_get_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'get_libvirt_version')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.volume_define')
    @mock.patch('devops.models.node.Node.has_snapshot')
    def test_update_disks_from_snapshot_with_children(
            self, mock_has_snapshot, mock_volume_define,
            mock_libvirt_version,
            mock_get_snapshot, mock_create_snapshot):
        mock_has_snapshot.return_value = False
        mock_libvirt_version.return_value = 1002012
        volume_path_template = '/var/lib/libvirt/images/{0}'

        environment = Environment.create('test_env_extsnap')
        node = Node.node_create(name='test_node', environment=environment)
        vol_volume_name = factories.fuzzy_string()
        vol = Volume.volume_create(vol_volume_name,
                                   capacity=1000000000,
                                   format='qcow2',
                                   environment=environment)
        vol.uuid = volume_path_template.format(vol_volume_name)
        DiskDevice.node_attach_volume(node=node, volume=vol)
        environment.define()

        snap_name = factories.fuzzy_string('snap_')
        snap_description = factories.fuzzy_string('description_')
        snapshot_volume_name = '{0}.{1}'.format(vol_volume_name,
                                                snap_name)
        mock_get_snapshot.return_value = mock.Mock(
            get_type='external', children_num=1,
            disks={'sda': volume_path_template.format(snap_name)})

        node.snapshot(name=snap_name, description=snap_description,
                      external=True)
        vol1 = environment.get_volume(name=snapshot_volume_name)
        vol1.uuid = volume_path_template.format(snap_name)
        vol1.save()

        node._update_disks_from_snapshot(snap_name)
        self.assertEqual(node.disk_devices[0].volume, vol)

    @pytest.mark.xfail(reason='to rewrite')
    @mock.patch('devops.models.node.Node._update_disks_from_snapshot')
    @mock.patch('devops.models.node.Node.destroy')
    @mock.patch('devops.models.node.Node.has_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.node_get_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'node_revert_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'node_revert_snapshot_recreate_disks')
    def test_external_snapshot_revert_no_children(
            self, mock_revert_snapshot_recreate_disks,
            mock_revert_snapshot, mock_get_snapshot, mock_has_snapshot,
            mock_destroy, mock_update_disks_from_snapshot):
        mock_has_snapshot.return_value = True
        mock_get_snapshot.return_value = mock.Mock(get_type='external',
                                                   children_num=0)

        environment = Environment.create('test_env_extsnap')
        node = Node.node_create(name='test_node', environment=environment)
        environment.define()
        snapshot_name = factories.fuzzy_string('snap_')
        node.revert(name=snapshot_name, destroy=False)

        mock_update_disks_from_snapshot.assert_called_with(snapshot_name)
        mock_revert_snapshot_recreate_disks.assert_called_with(
            node, snapshot_name)
        mock_revert_snapshot.assert_called_with(node=node, name=snapshot_name)

    @pytest.mark.xfail(reason='to rewrite')
    @mock.patch('devops.models.node.Node._update_disks_from_snapshot')
    @mock.patch('devops.models.node.Node.destroy')
    @mock.patch('devops.models.node.Node.has_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.node_get_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'node_revert_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'node_revert_snapshot_recreate_disks')
    def test_external_snapshot_revert_with_children_revert_present(
            self, mock_revert_snapshot_recreate_disks,
            mock_revert_snapshot, mock_get_snapshot, mock_has_snapshot,
            mock_destroy, mock_update_disks_from_snapshot):
        revert_postfix = '-revert3'

        def get_snapshot(node, snapname):
            if snapname.endswith(revert_postfix):
                return mock.Mock(get_type='external', children_num=0)
            else:
                return mock.Mock(get_type='external', children_num=1)

        mock_has_snapshot.return_value = True
        mock_get_snapshot.side_effect = get_snapshot
        environment = Environment.create('test_env_extsnap')
        node = Node.node_create(name='test_node', environment=environment)
        environment.define()
        snapshot_name = factories.fuzzy_string('snap_')
        node.revert(name=snapshot_name, destroy=False)

        revert_snapshot_name = '{0}{1}'.format(snapshot_name, revert_postfix)
        mock_update_disks_from_snapshot.assert_called_with(
            revert_snapshot_name)
        mock_revert_snapshot_recreate_disks.assert_called_with(
            node, revert_snapshot_name)
        mock_revert_snapshot.assert_called_with(node=node,
                                                name=revert_snapshot_name)

    @pytest.mark.xfail(reason='to rewrite')
    @mock.patch('devops.models.node.Node._update_disks_from_snapshot')
    @mock.patch('devops.models.node.Node.destroy')
    @mock.patch('devops.models.node.Node.has_snapshot')
    @mock.patch('devops.models.node.Node.snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.node_get_snapshot')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.'
        'node_revert_snapshot')
    def test_external_snapshot_revert_with_children_no_revert(
            self, mock_revert_snapshot, mock_get_snapshot,
            mock_do_snapshot, mock_has_snapshot,
            mock_destroy, mock_update_disks_from_snapshot):
        revert_postfix = '-revert'

        def has_snapshot(snapname):
            return not snapname.endswith(revert_postfix)

        mock_has_snapshot.side_effect = has_snapshot
        mock_get_snapshot.return_value = mock.Mock(get_type='external',
                                                   children_num=1)
        environment = Environment.create('test_env_extsnap')
        node = Node.node_create(name='test_node', environment=environment)
        environment.define()
        snapshot_name = factories.fuzzy_string('snap_')
        node.revert(name=snapshot_name, destroy=False)

        revert_snapshot_name = '{0}{1}'.format(snapshot_name, revert_postfix)
        mock_update_disks_from_snapshot.assert_called_with(snapshot_name)
        mock_do_snapshot.assert_called_with(name=revert_snapshot_name,
                                            external=True)
        mock_revert_snapshot.assert_called_with(node=node,
                                                name=snapshot_name)

    @pytest.mark.xfail(reason='to rewrite')
    @mock.patch(
        'devops.driver.libvirt.libvirt_driver.DevopsDriver.volume_define')
    def test_external_snapshot_volume_creation(self, mock_volume_define):
        mock_volume_define.return_value = None

        environment = Environment.create('test_env_extsnap')
        node = Node.node_create(name='test_node', environment=environment)
        vol_volume_name = factories.fuzzy_string()
        vol = Volume.volume_create(vol_volume_name,
                                   capacity=1000000000,
                                   format='qcow2',
                                   environment=environment)
        DiskDevice.node_attach_volume(node=node, volume=vol)
        environment.define()

        snapshot_name = factories.fuzzy_string('snap_')
        snapshot_volume_name = '{0}.{1}'.format(vol_volume_name,
                                                snapshot_name)

        node.snapshot_create_volume(snapshot_name)

        vol1 = environment.get_volume(name=snapshot_volume_name)

        self.assertEqual(len(node.disk_devices), 1)
        self.assertEqual(vol1.name, snapshot_volume_name)
        self.assertEqual(vol1.format, 'qcow2')
        self.assertEqual(vol1.environment, environment)
        self.assertEqual(vol1.backing_store, vol)
        self.assertEqual(vol1, node.disk_devices[0].volume)
        mock_volume_define.assert_called_with(vol1)
