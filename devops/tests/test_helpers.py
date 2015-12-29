# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

import unittest

from devops.helpers import helpers
from devops.helpers.network import IpNetworksPool
from devops.helpers.network import DevopsIPNetwork


class TestSnaphotList(unittest.TestCase):

    def test_get_keys(self):
        keys = helpers.get_keys(
            'IP',
            'NETMASK',
            'GW',
            'HOSTNAME',
            'NAT_INTERFACE',
            'DNS1',
            'SHOWMENU',
            'BUILD_IMAGES'
        )

        self.assertIn('<Wait>\n<Esc>\n<Wait>\n', keys)
        self.assertIn('ip=IP', keys)
        self.assertIn('netmask=NETMASK', keys)
        self.assertIn('gw=GW', keys)
        self.assertIn('dns1=DNS1', keys)
        self.assertIn('hostname=HOSTNAME', keys)
        self.assertIn('dhcp_interface=NAT_INTERFACE', keys)
        self.assertIn('showmenu=SHOWMENU', keys)
        self.assertIn('build_images=BUILD_IMAGES', keys)


class TestNetworkHelpers(unittest.TestCase):

    def test_getting_subnetworks(self):
        pool = IpNetworksPool([DevopsIPNetwork('10.1.0.0/22')], 24)
        networks = list(pool)
        assert len(networks) == 4
        assert (DevopsIPNetwork('10.1.0.0/24') in networks) is True
        assert (DevopsIPNetwork('10.1.1.0/24') in networks) is True
        assert (DevopsIPNetwork('10.1.2.0/24') in networks) is True
        assert (DevopsIPNetwork('10.1.3.0/24') in networks) is True

    def test_getting_subnetworks_alloceted(self):
        pool = IpNetworksPool(
            networks=[DevopsIPNetwork('10.1.0.0/22')], prefix=24,
            allocated_networks=[
                DevopsIPNetwork('10.1.1.0/24'),
                DevopsIPNetwork('10.1.3.0/24'),
            ])
        networks = list(pool)
        assert len(networks) == 2
        assert (DevopsIPNetwork('10.1.0.0/24') in networks) is True
        assert (DevopsIPNetwork('10.1.1.0/24') not in networks) is True
        assert (DevopsIPNetwork('10.1.2.0/24') in networks) is True
        assert (DevopsIPNetwork('10.1.3.0/24') not in networks) is True

    def test_getting_ips(self):
        assert '10.1.0.254' == str(DevopsIPNetwork('10.1.0.0/24').ip_end)
        assert '10.1.0.2' == str(DevopsIPNetwork('10.1.0.0/24').ip_start)
        assert '10.1.0.1' == str(DevopsIPNetwork('10.1.0.0/24').default_gw)
