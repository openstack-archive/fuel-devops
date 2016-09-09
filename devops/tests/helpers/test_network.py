# -*- coding: utf-8 -*-

#    Copyright 2015 - 2016 Mirantis, Inc.
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

import unittest

import netaddr

from devops.helpers import network


class TestNetworkHelpers(unittest.TestCase):

    def test_getting_subnetworks(self):
        pool = network.IpNetworksPool([netaddr.IPNetwork('10.1.0.0/22')], 24)
        networks = list(pool)
        assert len(networks) == 4
        assert (netaddr.IPNetwork('10.1.0.0/24') in networks) is True
        assert (netaddr.IPNetwork('10.1.1.0/24') in networks) is True
        assert (netaddr.IPNetwork('10.1.2.0/24') in networks) is True
        assert (netaddr.IPNetwork('10.1.3.0/24') in networks) is True

    def test_getting_subnetworks_allocated(self):
        pool = network.IpNetworksPool(
            networks=[netaddr.IPNetwork('10.1.0.0/22')], prefix=24,
            allocated_networks=[
                netaddr.IPNetwork('10.1.1.0/24'),
                netaddr.IPNetwork('10.1.3.0/24'),
            ])
        networks = list(pool)
        assert len(networks) == 2
        assert (netaddr.IPNetwork('10.1.0.0/24') in networks) is True
        assert (netaddr.IPNetwork('10.1.1.0/24') not in networks) is True
        assert (netaddr.IPNetwork('10.1.2.0/24') in networks) is True
        assert (netaddr.IPNetwork('10.1.3.0/24') not in networks) is True
