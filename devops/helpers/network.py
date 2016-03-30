#    Copyright 2013 - 2014 Mirantis, Inc.
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
from netaddr import IPSet


class IpNetworksPool(object):
    def __init__(self, networks, prefix):
        self.networks = networks
        self.prefix = prefix
        self.allocated_networks = []
        self._initialize_generator()

    def set_allocated_networks(self, allocated_networks):
        self.allocated_networks = allocated_networks
        self._initialize_generator()

    @staticmethod
    def _overlaps(network, allocated_networks):
        return any((IPSet(network) & IPSet(an)) for an in allocated_networks)

    def _initialize_generator(self):
        def _get_generator():
            for network in self.networks:
                for sub_net in network.subnet(prefixlen=self.prefix):
                    if not self._overlaps(sub_net, self.allocated_networks):
                        yield sub_net

        self._generator = _get_generator()

    def __repr__(self):
        return '{0}({1}, {2})'.format(
            self.__class__.__name__,
            self.networks,
            self.prefix
        )

    def __iter__(self):
        return self._generator

    def next(self):
        return next(self._generator)
