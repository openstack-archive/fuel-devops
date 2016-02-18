#    Copyright 2013 - 2016 Mirantis, Inc.
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

from devops.models import Address
from devops.models import AddressPool
from devops.models import Environment
from devops.models import Interface
from devops.models import L2NetworkDevice
from devops.models import Node


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
