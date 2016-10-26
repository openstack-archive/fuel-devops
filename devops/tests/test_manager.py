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

# pylint: disable=no-self-use

from django.test import TestCase
import mock
import netaddr
import pytest

from devops import error
from devops.helpers import network
from devops import models


class TestManager(TestCase):

    def test_network_iterator(self):
        environment = models.Environment.create('test_env')
        group = environment.add_group(group_name='test-group',
                                      driver_name='devops.driver.empty')
        node = models.Node.objects.create(
            group=group,
            name='test_node',
            role='default',
        )
        pool = network.IpNetworksPool(
            networks=[netaddr.IPNetwork('10.1.0.0/24')], prefix=24)
        address_pool = models.AddressPool.address_pool_create(
            environment=environment, name='internal', pool=pool)
        l2_net_dev = models.L2NetworkDevice.objects.create(
            group=None, address_pool=address_pool, name='test_l2_dev')
        interface = models.Interface.interface_create(
            l2_network_device=l2_net_dev, node=node, label='eth0')
        assert str(address_pool.next_ip()) == '10.1.0.3'
        models.Address.objects.create(
            ip_address=str('10.1.0.3'), interface=interface)
        assert str(address_pool.next_ip()) == '10.1.0.4'
        models.Address.objects.create(
            ip_address=str('10.1.0.4'), interface=interface)
        assert str(address_pool.next_ip()) == '10.1.0.5'

    def test_network_model(self):
        environment = models.Environment.create('test_env')
        group = environment.add_group(group_name='test-group',
                                      driver_name='devops.driver.empty')
        node = models.Node.objects.create(
            group=group,
            name='test_node',
            role='default',
        )
        pool = network.IpNetworksPool(
            networks=[netaddr.IPNetwork('10.1.0.0/24')], prefix=24)
        address_pool = models.AddressPool.address_pool_create(
            environment=environment, name='internal', pool=pool)
        l2_net_dev = models.L2NetworkDevice.objects.create(
            group=None, address_pool=address_pool, name='test_l2_dev')

        interface1 = models.Interface.interface_create(
            l2_network_device=l2_net_dev, node=node, label='eth0')

        assert interface1.model == 'virtio'
        interface2 = models.Interface.interface_create(
            l2_network_device=l2_net_dev,
            node=node, label='eth0',
            model='e1000')
        assert interface2.model == 'e1000'

    def test_network_pool(self):
        environment = models.Environment.create('test_env2')
        self.assertEqual(
            '10.0.0.0/24',
            str(models.AddressPool.address_pool_create(
                environment=environment,
                name='internal',
                pool=None).ip_network))
        self.assertEqual(
            '10.0.1.0/24',
            str(models.AddressPool.address_pool_create(
                environment=environment,
                name='external',
                pool=None).ip_network))
        self.assertEqual(
            '10.0.2.0/24',
            str(models.AddressPool.address_pool_create(
                environment=environment,
                name='private',
                pool=None).ip_network))

        environment = models.Environment.create('test_env3')
        self.assertEqual(
            '10.0.3.0/24',
            str(models.AddressPool.address_pool_create(
                environment=environment,
                name='internal',
                pool=None).ip_network))
        self.assertEqual(
            '10.0.4.0/24',
            str(models.AddressPool.address_pool_create(
                environment=environment,
                name='external',
                pool=None).ip_network))
        self.assertEqual(
            '10.0.5.0/24',
            str(models.AddressPool.address_pool_create(
                environment=environment,
                name='private',
                pool=None).ip_network))

    def test_node_creation(self):
        environment = models.Environment.create('test_env3')
        group = environment.add_group(group_name='test-group',
                                      driver_name='devops.driver.empty')
        pool = network.IpNetworksPool(
            networks=[netaddr.IPNetwork('10.1.0.0/24')], prefix=24)
        address_pool = models.AddressPool.address_pool_create(
            environment=environment, name='internal', pool=pool)
        l2_net_dev = models.L2NetworkDevice.objects.create(
            group=None, address_pool=address_pool, name='test_l2_dev')

        node = models.Node.objects.create(
            group=group,
            name='test_node',
            role='default',
        )
        models.Interface.interface_create(
            l2_network_device=l2_net_dev, node=node, label='eth0')
        environment.define()

    def test_safe_create_network_no_address_avail(self):
        environment = models.Environment.create('test_env1')
        pool = network.IpNetworksPool(
            networks=[netaddr.IPNetwork('10.1.0.0/24')], prefix=24)
        models.AddressPool.address_pool_create(
            environment=environment, name='test_ap', pool=pool)
        with pytest.raises(error.DevopsError) as e:
            models.AddressPool.address_pool_create(
                environment=environment, name='test_ap2', pool=pool)
        assert str(e.value) == (
            'There is no network pool available '
            'for creating address pool test_ap2')

    def test_safe_create_network_race_condition(self):
        environment = models.Environment.create('test_env1')
        pool = network.IpNetworksPool(
            networks=[netaddr.IPNetwork('10.1.0.0/16')], prefix=24)
        ap1 = models.AddressPool.address_pool_create(
            environment=environment, name='test_ap1', pool=pool)
        assert ap1.net == netaddr.IPNetwork('10.1.0.0/24')
        ap2 = models.AddressPool.address_pool_create(
            environment=environment, name='test_ap2', pool=pool)
        assert ap2.net == netaddr.IPNetwork('10.1.1.0/24')

        real_create = models.AddressPool.objects.create

        def race_condition_side_effect(*args, **kwargs):
            # create ap with the same net
            e = models.Environment.create('test_env_other')
            real_create(
                name='test_ap',
                environment=e,
                net=netaddr.IPNetwork('10.1.2.0/24'))

            return real_create(*args, **kwargs)

        with mock.patch(
                'devops.models.network.AddressPool.objects.create',
                side_effect=race_condition_side_effect):

            ap3 = models.AddressPool.address_pool_create(
                environment=environment, name='test_ap3', pool=pool)
            assert ap3.net == netaddr.IPNetwork('10.1.3.0/24')

    def test_create_network_name_exists(self):
        environment = models.Environment.create('test_env1')
        pool = network.IpNetworksPool(
            networks=[netaddr.IPNetwork('10.1.0.0/16')], prefix=24)
        models.AddressPool.address_pool_create(
            environment=environment, name='test_ap1', pool=pool)
        with pytest.raises(error.DevopsError) as e:
            models.AddressPool.address_pool_create(
                environment=environment, name='test_ap1', pool=pool)
        assert str(e.value) == \
            'AddressPool with name "test_ap1" already exists'
