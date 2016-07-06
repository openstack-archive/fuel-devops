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
from devops import settings
from devops.tests.driver.libvirt.base import LibvirtTestCase


class TestK8sExt(LibvirtTestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        super(TestK8sExt, self).setUp()

        self.open_mock = mock.mock_open(read_data='image_data')
        self.patch('devops.driver.libvirt.libvirt_driver.open',
                   self.open_mock, create=True)

        self.os_mock = self.patch('devops.helpers.helpers.os')
        Size = collections.namedtuple('Size', ['st_size'])
        self.file_sizes = {
            '/tmp/test/cloud_settings.iso': Size(st_size=1 * 1024 ** 3),
        }
        self.os_mock.stat.side_effect = self.file_sizes.get

        self.generate_cloud_image_settings_mock = self.patch(
            'devops.models.node_ext.k8s.generate_cloud_image_settings')

        self.volume_upload_mock = self.patch(
            'devops.driver.libvirt.Volume.upload')

        # Environment with a 'public' network

        self.env = Environment.create('test')
        self.group = self.env.add_group(
            group_name='test_group',
            driver_name='devops.driver.libvirt',
            connection_string='test:///default',
            storage_pool_name='default-pool')

        self.pub_ap = self.env.add_address_pool(
            name='public-pool01', net='10.109.0.0/16:24', tag=0,
            ip_reserved=dict(gateway=1, l2_network_device=1),
            ip_ranges=dict(default=[2, -2]))
        self.group.add_l2_network_device(
            name='public', address_pool='public-pool01')

        # Node connected to the 'public' network

        self.node = self.group.add_node(
            name='test-node',
            role='k8s',
            architecture='x86_64',
            hypervisor='test',
            cloud_init_volume_name='iso',
            cloud_init_iface_up='enp0s3')

        self.system_volume = self.node.add_volume(name='system')
        self.iso_volume = self.node.add_volume(name='iso')

        self.adm_iface = self.node.add_interface(
            label='enp0s3',
            l2_network_device_name='public',
            mac_address='64:b6:87:44:14:17',
            interface_model='e1000')

        self.node.add_network_config(
            label='enp0s3',
            networks=['public'])

    @mock.patch('devops.driver.libvirt.libvirt_driver.uuid')
    @mock.patch('libvirt.virConnect.defineXML')
    @mock.patch.multiple(settings, CLOUD_IMAGE_DIR='/tmp/')
    def test_post_define(self, define_xml_mock, uuid_mock):
        uuid_mock.uuid4.side_effect = (
            mock.Mock(hex='fe527bd28e0f4a84b9117dc97142c580'),
            mock.Mock(hex='9cddb80fe82e480eb14c1a89f1c0e11d'),
            mock.Mock(hex='885674d28e0f4a84b265625673674565'),
            mock.Mock(hex='91252350fe82e480eb14c1a89f1c0234'))
        define_xml_mock.return_value.UUIDString.return_value = 'fake_uuid'

        self.system_volume.define()
        self.iso_volume.define()
        self.node.define()

        self.generate_cloud_image_settings_mock.assert_called_once_with(
            admin_ip='10.109.0.2',
            admin_netmask='255.255.255.0',
            admin_network='10.109.0.0/24',
            cloud_image_settings_path='/tmp/test/cloud_settings.iso',
            meta_data_content=None,
            meta_data_path='/tmp/test/meta-data',
            user_data_content=None,
            user_data_path='/tmp/test/user-data',
            dns='8.8.8.8', dns_ext='8.8.8.8',
            gateway='10.109.0.1',
            hostname='test-node',
            interface_name='enp0s3',
            password='r00tme',
            user='root')
        self.volume_upload_mock.assert_called_once_with(
            '/tmp/test/cloud_settings.iso')
