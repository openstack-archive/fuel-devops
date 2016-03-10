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

from django.test import TestCase

from devops.models import Environment


class DriverlessTestCase(TestCase):

    def setUp(self):
        # ENVIRONMENT
        self.env = Environment.create(name='test')

        # ADRESS POOLS
        self.admin_ap = self.env.add_address_pool(
            name='fuelweb_admin-pool01', net='10.109.0.0/16:24', tag=0)
        self.pub_ap = self.env.add_address_pool(
            name='public-pool01', net='10.109.0.0/16:24', tag=0)
        self.stor_ap = self.env.add_address_pool(
            name='storage-pool01', net='10.109.0.0/16:24', tag=101)
        self.mng_ap = self.env.add_address_pool(
            name='management-pool01', net='10.109.0.0/16:24', tag=102)
        self.priv_ap = self.env.add_address_pool(
            name='private-pool01', net='10.109.0.0/16:24', tag=103)

        # GROUP
        self.group = self.env.add_group(group_name='test-group',
                                        driver_name='devops.models')

        # NETWORK POOLS
        self.group.add_network_pool(name='fuelweb_admin',
                                    address_pool_name='fuelweb_admin-pool01')
        self.group.add_network_pool(name='public',
                                    address_pool_name='public-pool01')
        self.group.add_network_pool(name='storage',
                                    address_pool_name='storage-pool01')
        self.group.add_network_pool(name='management',
                                    address_pool_name='management-pool01')
        self.group.add_network_pool(name='private',
                                    address_pool_name='private-pool01')

        # L2 NETWORK DEVICES
        self.group.add_l2_network_device(
            name='admin', address_pool_name='fuelweb_admin-pool01')
        self.group.add_l2_network_device(
            name='public', address_pool_name='public-pool01')
        self.group.add_l2_network_device(
            name='storage', address_pool_name='storage-pool01')
        self.group.add_l2_network_device(
            name='management', address_pool_name='management-pool01')
        self.group.add_l2_network_device(
            name='private', address_pool_name='private-pool01')
