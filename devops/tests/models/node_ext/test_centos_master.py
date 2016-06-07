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

import netaddr
import mock

from devops import settings
from devops.tests.driver.driverless import DriverlessTestCase


class TestCentosMasterExt(DriverlessTestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        super(TestCentosMasterExt, self).setUp()

        self.node = self.group.add_node(
            name='test-node',
            role='centos_master')
        self.node.add_volume(
            name='system')
        self.node.add_volume(
            name='iso')

        self.adm_iface = self.node.add_interface(
            label='enp0s3',
            l2_network_device_name='admin',
            interface_model='e1000')

        self.node.add_network_config(
            label='eth0',
            networks=['fuelweb_admin'])

        self.wait_tcp_mock = self.patch(
            'devops.models.node_ext.centos_master.wait_tcp')

        self.generate_cloud_image_settings_mock = self.patch(
            'devops.models.node_ext.'
            'centos_master.generate_cloud_image_settings')

        self.volume_upload_mock = self.patch(
            'devops.models.volume.Volume.upload', create=True)

        self.node_ext = self.node.ext

    @mock.patch.multiple(settings, CLOUD_IMAGE_DIR='/mydir/')
    def test_post_define(self):
        self.node.define()
        self.generate_cloud_image_settings_mock.assert_called_once_with(
            admin_ip='10.109.0.2',
            admin_netmask=str(netaddr.IPAddress('255.255.255.0')),
            admin_network=str(netaddr.IPNetwork('10.109.0.0/24')),
            cloud_image_settings_path='/mydir/cloud_settings.iso',
            dns='8.8.8.8', dns_ext='8.8.8.8',
            gateway='10.109.0.1',
            hostname='nailgun.domain.local',
            interface_name=u'enp0s3',
            password='r00tme',
            user='root')
        self.volume_upload_mock.assert_called_once_with(
            '/mydir/cloud_settings.iso')
