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
from netaddr import IPNetwork

from devops.models import Environment
from devops.tests.driver.libvirt.base import LibvirtTestCase


class TestLibvirtL2NetworkDevice(LibvirtTestCase):

    def setUp(self):
        super(TestLibvirtL2NetworkDevice, self).setUp()

        self.env = Environment.create('test_env')
        self.group = self.env.add_group(
            group_name='test_group',
            driver_name='devops.driver.libvirt.libvirt_driver',
            connection_string='test:///default')

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
            forward=dict(mode='nat'),
            address_pool='test_ap',
        )

        self.d = self.group.driver

    def test_define(self):
        assert self.l2_net_dev.forward.mode == 'nat'
        self.l2_net_dev.define()
        assert isinstance(self.l2_net_dev.uuid, str)
        assert len(self.l2_net_dev.uuid) == 36
        assert self.l2_net_dev.network_name == 'test_env_test_l2_net_dev'
        assert self.l2_net_dev.exists() is True
        assert self.l2_net_dev.is_active() == 0
        assert self.l2_net_dev.bridge_name() == 'virbr1'
        assert self.l2_net_dev._libvirt_network.autostart() == 1

        xml = self.l2_net_dev._libvirt_network.XMLDesc(0)
        assert xml == (
            "<network>\n"
            "  <name>test_env_test_l2_net_dev</name>\n"
            "  <uuid>{0}</uuid>\n"
            "  <forward mode='nat'/>\n"
            "  <bridge name='virbr1' stp='on' delay='0'/>\n"
            "  <ip address='172.0.0.1' prefix='24'>\n"
            "  </ip>\n"
            "</network>\n".format(self.l2_net_dev.uuid))

    def test_start_destroy(self):
        self.l2_net_dev.define()
        assert self.l2_net_dev.is_active() == 0
        self.l2_net_dev.start()
        assert self.l2_net_dev.is_active() == 1
        self.l2_net_dev.destroy()
        assert self.l2_net_dev.is_active() == 0

    def test_exists(self):
        self.l2_net_dev.define()
        assert self.l2_net_dev.exists() is True
        self.l2_net_dev.remove()
        assert self.l2_net_dev.exists() is False

    # speed up retry
    @mock.patch('devops.helpers.retry.sleep')
    def test_remove_active(self, sleep_mock):
        self.l2_net_dev.define()
        self.l2_net_dev.start()
        assert self.l2_net_dev.exists() is True
        assert self.l2_net_dev.is_active() == 1

        self.l2_net_dev.remove()
        assert self.l2_net_dev.exists() is False
        # raises libvirtError
        # assert self.l2_net_dev.is_active() == 0

    def test_driver_get_allocated_networks(self):
        self.l2_net_dev.define()

        ret = self.d.get_allocated_networks()
        assert len(ret) == 1
        assert ret[0] == IPNetwork('172.0.0.1/24')
