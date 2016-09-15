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
import netaddr


class IpNetworksPool(object):

    def __init__(self, networks, prefix, allocated_networks=None):
        if allocated_networks is None:
            allocated_networks = []

        self.networks = networks
        self.prefix = prefix
        self.allocated_networks = allocated_networks

    @staticmethod
    def _overlaps(network, allocated_networks):
        return any(
            (netaddr.IPSet(network) & netaddr.IPSet(an))
            for an in allocated_networks)

    def __iter__(self):
        for network in self.networks:
            for sub_net in network.subnet(prefixlen=self.prefix):
                if not self._overlaps(sub_net, self.allocated_networks):
                    yield sub_net

    def __repr__(self):
        return "{}(networks={}, prefix={}, allocated_networks={})".format(
            self.__class__.__name__, self.networks, self.prefix,
            self.allocated_networks
        )
