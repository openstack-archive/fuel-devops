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

from ipaddr import IPNetwork

from devops.helpers import helpers
from devops.helpers.network import IpNetworksPool


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
        self.assertIn('ip=IP::GW:NETMASK:HOSTNAME:enp0s3:none', keys)
        self.assertIn('netmask=NETMASK', keys)
        self.assertIn('gw=GW', keys)
        self.assertIn('dns1=DNS1', keys)
        self.assertIn('nameserver=DNS1', keys)
        self.assertIn('hostname=HOSTNAME', keys)
        self.assertIn('dhcp_interface=NAT_INTERFACE', keys)
        self.assertIn('showmenu=SHOWMENU', keys)
        self.assertIn('build_images=BUILD_IMAGES', keys)

    def test_get_keys_centos6(self):
        keys = helpers.get_keys(
            ip='IP',
            mask='NETMASK',
            gw='GW',
            hostname='HOSTNAME',
            nat_interface='NAT_INTERFACE',
            dns1='DNS1',
            showmenu='SHOWMENU',
            build_images='BUILD_IMAGES',
            centos_version=6
        )

        self.assertIn('<Wait>\n<Esc>\n<Wait>\n', keys)
        self.assertIn('ip=IP', keys)
        self.assertIn('netmask=NETMASK', keys)
        self.assertIn('gw=GW', keys)
        self.assertIn('dns1=DNS1', keys)
        self.assertIn('nameserver=DNS1', keys)
        self.assertIn('hostname=HOSTNAME', keys)
        self.assertIn('dhcp_interface=NAT_INTERFACE', keys)
        self.assertIn('showmenu=SHOWMENU', keys)
        self.assertIn('build_images=BUILD_IMAGES', keys)


class TestNetworkHelpers(unittest.TestCase):

    def test_getting_subnetworks(self):
        pool = IpNetworksPool([IPNetwork('10.1.0.0/22')], 24)
        networks = list(pool)
        assert len(networks) == 4
        assert (IPNetwork('10.1.0.0/24') in networks) is True
        assert (IPNetwork('10.1.1.0/24') in networks) is True
        assert (IPNetwork('10.1.2.0/24') in networks) is True
        assert (IPNetwork('10.1.3.0/24') in networks) is True

    def test_getting_subnetworks_alloceted(self):
        pool = IpNetworksPool(
            networks=[IPNetwork('10.1.0.0/22')], prefix=24,
            allocated_networks=[
                IPNetwork('10.1.1.0/24'),
                IPNetwork('10.1.3.0/24'),
            ])
        networks = list(pool)
        assert len(networks) == 2
        assert (IPNetwork('10.1.0.0/24') in networks) is True
        assert (IPNetwork('10.1.1.0/24') not in networks) is True
        assert (IPNetwork('10.1.2.0/24') in networks) is True
        assert (IPNetwork('10.1.3.0/24') not in networks) is True
