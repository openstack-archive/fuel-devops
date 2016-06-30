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

import xml.etree.ElementTree as ET

from django.test import TestCase
import mock
from netaddr import IPNetwork

from devops.driver.libvirt.libvirt_driver import _LibvirtManager
from devops.driver.libvirt.libvirt_driver import LibvirtDriver
from devops.models import Environment
from devops.tests.driver.libvirt.base import LibvirtTestCase


class TestLibvirtManager(TestCase):

    def setUp(self):
        self.libvirt_patcher = mock.patch(
            'devops.driver.libvirt.libvirt_driver.libvirt',
            autospec=True)
        self.libvirt_mock = self.libvirt_patcher.start()

        self.manager = _LibvirtManager()

    def tearDown(self):
        self.libvirt_patcher.stop()

    def test_init(self):
        self.libvirt_mock.virInitialize.assert_called_once_with()
        assert self.manager.connections == {}

    def test_get_connection(self):
        assert self.manager.connections == {}

        # get connection
        c = self.manager.get_connection('qemu:///system')

        self.libvirt_mock.open.assert_called_once_with('qemu:///system')
        assert c is self.libvirt_mock.open.return_value
        assert self.manager.connections == {'qemu:///system': c}

        # get the same connection
        c2 = self.manager.get_connection('qemu:///system')

        self.libvirt_mock.open.assert_called_once_with('qemu:///system')
        assert c2 is c
        assert self.manager.connections == {'qemu:///system': c}

        self.libvirt_mock.open.reset_mock()

        # get another connection
        c3 = self.manager.get_connection('test:///default')

        self.libvirt_mock.open.assert_called_once_with('test:///default')
        assert c is self.libvirt_mock.open.return_value
        assert self.manager.connections == {'qemu:///system': c,
                                            'test:///default': c3}


class TestLibvirtDriver(LibvirtTestCase):

    def setUp(self):
        super(TestLibvirtDriver, self).setUp()

        self.env = Environment.create('test_env')
        self.group = self.env.add_group(
            group_name='test_group',
            driver_name='devops.driver.libvirt',
            connection_string='test:///default')

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

        self.d = self.group.driver

        self.node = None

    def test_create(self):
        assert isinstance(self.d, LibvirtDriver)
        assert self.d.connection_string == 'test:///default'
        assert self.d.storage_pool_name == 'default'
        assert self.d.stp is True
        assert self.d.hpet is True
        assert self.d.use_host_cpu is True
        assert self.d.reboot_timeout is None
        assert self.d.use_hugepages is False
        assert self.d.vnc_password is None

        assert self.d.conn is not None

    def test_get_capabilities(self):
        assert isinstance(self.d.get_capabilities(), ET.Element)

    def test_get_node_list(self):
        assert self.d.node_list() == []
        self.node = self.group.add_node(
            name='test_node',
            role='default',
            architecture='i686',
            hypervisor='test',
        )
        self.node.define()
        assert self.d.node_list() == ['test_env_test_node']

    def test_get_allocated_networks(self):
        self.d.conn.networkDefineXML(
            '<?xml version="1.0" encoding="utf-8" ?>\n'
            '<network>\n'
            '    <name>test_name</name>\n'
            '    <bridge delay="0" name="virbr13" stp="on" />\n'
            '    <forward mode="nat" />\n'
            '    <ip address="172.0.1.1" prefix="24" />\n'
            '</network>'
        )
        ret = self.d.get_allocated_networks()
        assert len(ret) == 1
        assert ret[0] == IPNetwork('172.0.1.1/24')

    def test_get_version(self):
        assert isinstance(self.d.get_libvirt_version(), int)
