#    Copyright 2014 Mirantis, Inc.
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
from ipaddr import IPNetwork, IPv4Network
from devops.helpers.network import IpNetworksPool
from devops.manager import Manager


class TestManager(TestCase):
    manager = Manager()

    def tearDown(self):
        for environment in self.manager.environment_list():
            environment.erase()

    def test_getting_subnetworks(self):
        pool = IpNetworksPool(networks=[IPNetwork('10.1.0.0/22')], prefix=24)
        pool.set_allocated_networks([IPv4Network('10.1.1.0/24')])
        networks = list(pool)
        self.assertTrue(IPv4Network('10.1.0.0/24') in networks)
        self.assertFalse(IPv4Network('10.1.1.0/24') in networks)
        self.assertTrue(IPv4Network('10.1.2.0/24') in networks)
        self.assertTrue(IPv4Network('10.1.3.0/24') in networks)

    def test_getting_ips(self):
        self.assertEquals('10.1.0.254', str(IPv4Network('10.1.0.0/24')[-2]))

    def test_network_iterator(self):
        environment = self.manager.environment_create('test_env')
        node = self.manager.node_create('test_node', environment)
        network = self.manager.network_create(
            environment=environment, name='internal', ip_network='10.1.0.0/24')
        interface = self.manager.interface_create(network=network, node=node)
        self.manager.network_create_address(str('10.1.0.1'),
                                            interface=interface)
        ip = network.next_ip()
        self.manager.network_create_address(str('10.1.0.3'),
                                            interface=interface)
        ip = network.next_ip()
        self.assertEquals('10.1.0.4', str(ip))

    def test_network_model(self):
        environment = manager.environment_create('test_env')
        node = self.manager.node_create('test_node', environment)
        network = self.manager.network_create(
            environment=environment, name='internal', ip_network='10.1.0.0/24')
        interface1 = self.manager.interface_create(network=network, node=node)
        self.assertEquals('virtio', interface1.model)
        interface2 = self.manager.interface_create(
            network=network, node=node, model='e1000')
        self.assertEquals('e1000', interface2.model)

    def test_environment_values(self):
        environment = self.manager.environment_create('test_env')
        print environment.volumes

    def test_network_pool(self):
        environment = self.manager.environment_create('test_env2')
        self.assertEqual('10.0.0.0/24', str(self.manager.network_create(
            environment=environment, name='internal', pool=None).ip_network))
        self.assertEqual('10.0.1.0/24', str(self.manager.network_create(
            environment=environment, name='external', pool=None).ip_network))
        self.assertEqual('10.0.2.0/24', str(self.manager.network_create(
            environment=environment, name='private', pool=None).ip_network))
        environment = self.manager.environment_create('test_env2')
        self.assertEqual('10.0.3.0/24', str(self.manager.network_create(
            environment=environment, name='internal', pool=None).ip_network))
        self.assertEqual('10.0.4.0/24', str(self.manager.network_create(
            environment=environment, name='external', pool=None).ip_network))
        self.assertEqual('10.0.5.0/24', str(self.manager.network_create(
            environment=environment, name='private', pool=None).ip_network))

    def test_node_creationw(self):
        environment = self.manager.environment_create('test_env55')
        node = self.manager.node_create(
            name='test_node4',
            environment=environment)
        node.define()

    def test_node_creation(self):
        environment = self.manager.environment_create('test_env3')
        internal = self.manager.network_create(
            environment=environment, name='internal', pool=None)
        node = self.manager.node_create(
            name='test_node', environment=environment)
        self.manager.interface_create(node=node, network=internal)
        environment.define()

    def test_create_volume(self):
        environment = self.manager.environment_create('test_env3')
        volume = self.manager.volume_get_predefined(
            '/var/lib/libvirt/images/disk-135824657433.qcow2')
        v3 = self.manager.volume_create_child(
            'test_vp89', backing_store=volume, environment=environment)
        v3.define()

    def test_create_volume(self):
        volume = self.manager.volume_get_predefined(
            '/var/lib/libvirt/images/disk-135824657433.qcow2')
        v3 = self.manager.volume_create_child(
            'test_vp89', backing_store=volume)
        v3.define()

    def test_create_node3(self):
        environment = self.manager.environment_create('test_env3')
        internal = self.manager.network_create(
            environment=environment, name='internal', pool=None)
        external = self.manager.network_create(
            environment=environment, name='external', pool=None)
        private = self.manager.network_create(
            environment=environment, name='private', pool=None)
        node = self.manager.node_create(name='test_node',
                                        environment=environment)
        self.manager.interface_create(node=node, network=internal)
        self.manager.interface_create(node=node, network=external)
        self.manager.interface_create(node=node, network=private)
        volume = self.manager.volume_get_predefined(
            '/var/lib/libvirt/images/disk-135824657433.qcow2')
        v3 = self.manager.volume_create_child('test_vp892',
                                              backing_store=volume,
                                              environment=environment)
        v4 = self.manager.volume_create_child('test_vp891',
                                              backing_store=volume,
                                              environment=environment)
        self.manager.node_attach_volume(node=node, volume=v3)
        self.manager.node_attach_volume(node, v4)
        environment.define()
