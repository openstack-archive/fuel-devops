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

import collections

import mock

from devops.models import Environment
from devops.tests.driver.libvirt.base import LibvirtTestCase


class TestLibvirtVolumeBackingStore(LibvirtTestCase):

    def setUp(self):
        super(TestLibvirtVolumeBackingStore, self).setUp()

        self.sleep_mock = self.patch('time.sleep')

        self.open_mock = mock.mock_open(read_data='image_data')
        self.patch('devops.driver.libvirt.libvirt_driver.open',
                   self.open_mock, create=True)

        self.os_mock = self.patch('devops.helpers.helpers.os')
        # noinspection PyPep8Naming
        Size = collections.namedtuple('Size', ['st_size'])
        self.file_sizes = {
            '/tmp/admin.iso': Size(st_size=500),
        }
        self.os_mock.stat.side_effect = self.file_sizes.get

        self.env = Environment.create('test_env')
        self.group1 = self.env.add_group(
            group_name='test_group1',
            driver_name='devops.driver.libvirt',
            connection_string='test:///default',
            storage_pool_name='default-pool')
        self.group2 = self.env.add_group(
            group_name='test_group2',
            driver_name='devops.driver.libvirt',
            connection_string='test:///default',
            storage_pool_name='default-pool')

        self.node1 = self.group1.add_node(
            name='test_node1',
            role='default',
            architecture='i686',
            hypervisor='test',
        )

        self.node2 = self.group1.add_node(
            name='test_node2',
            role='default',
            architecture='i686',
            hypervisor='test',
        )

    def test_backing_store(self):
        parent_vol1 = self.group1.add_volume(
            name='parent_volume',
            format='qcow2',
            capacity=10,
            source_image='/tmp/admin.iso',
        )
        parent_vol1.define()

        parent_vol2 = self.group2.add_volume(
            name='parent_volume',
            format='qcow2',
            capacity=10,
            source_image='/tmp/admin.iso',
        )
        parent_vol2.define()

        child_volume1 = self.node1.add_volume(
            name='test_volume1',
            backing_store='parent_volume',
            capacity=20,
        )
        child_volume1.define()

        assert child_volume1.capacity == 20
        assert child_volume1.backing_store is not None
        assert child_volume1.backing_store.pk == parent_vol1.pk

        child_volume2 = self.node2.add_volume(
            name='test_volume2',
            backing_store='parent_volume',
            capacity=20,
        )
        child_volume2.define()

        assert child_volume2.capacity == 20
        assert child_volume2.backing_store is not None
        assert child_volume2.backing_store.pk == parent_vol1.pk
