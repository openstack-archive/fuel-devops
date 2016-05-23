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


import mock
import yaml

from devops.driver.baremetal.ipmi_client import IpmiClient
from devops.models import Environment
from django.test import TestCase

ENV_TMPLT = """
---
aliases:

  dynamic_address_pool:
   - &pool_default 10.109.0.0/16:24

  default_interface_model:
   - &interface_model e1000

template:
  devops_settings:
    env_name: test_ipmi

    address_pools:
    # Network pools used by the environment
      fuelweb_admin-pool01:
        net: *pool_default
        params:
          tag: 0

    groups:
     - name: baremetal-rack-01
       driver:
         name: devops.driver.baremetal

       network_pools:  # Address pools for OpenStack networks.
         # Actual names should be used for keys
         # (the same as in Nailgun, for example)
         fuelweb_admin: fuelweb_admin-pool01

       l2_network_devices:  # bridges. It is *NOT* Nailgun networks
         switch01:
           address_pool: fuelweb_admin-pool01

       nodes:
        - name: slave-01  # Custom name of baremetal for Fuel slave node
          role: fuel_slave  # Fixed role for Fuel master node properties
          params:
            ipmi_user: user1
            ipmi_password: pass1
            ipmi_previlegies: OPERATOR
            ipmi_host: ipmi-1.host.address.net
            ipmi_lan_interface: lanplus
            ipmi_port: 623

            # so, interfaces can be turn on in one or in a different switches.
            interfaces: # First interface is not used
             - label: iface2
               l2_network_device: switch01
            network_config:
             iface2:
                 networks:
                    - fuelweb_admin  ## OpenStack network, NOT switch name

        - name: slave-02  # Custom name of baremetal for Fuel slave node
          role: fuel_slave  # Fixed role for Fuel master node properties
          params:
            ipmi_user: user2
            ipmi_password: pass2
            ipmi_previlegies: OPERATOR
            ipmi_host: ipmi-2.host.address.net
            ipmi_lan_interface: lanplus
            ipmi_port: 623

            # so, interfaces can be turn on in one or in a different switches
            interfaces: # First interface is not used
             - label: iface2
               l2_network_device: switch01
            network_config:
              iface2:
                 networks:
                    - fuelweb_admin  ## OpenStack network, NOT switch name
"""


class TestIPMITemplate(TestCase):
    """ IPMI test template class """

    def patch(self, *args, **kwargs):
        """ specific path fucntion for mock """
        patcher = mock.patch(*args, **kwargs)
        mtmp = patcher.start()
        self.addCleanup(patcher.stop)
        return mtmp

    def setUp(self):
        super(TestIPMITemplate, self).setUp()

        # Create Environment
        self.full_conf = yaml.load(ENV_TMPLT)
        self.env = Environment.create_environment(self.full_conf)
        self.ipmiclient_mock = self.patch(
            'devops.driver.baremetal.ipmi_driver.IpmiClient')
        self.wait_mock = self.patch(
            'devops.driver.baremetal.ipmi_driver.wait')
        self.ipmiclient1 = mock.Mock(spec=IpmiClient)
        self.ipmiclient2 = mock.Mock(spec=IpmiClient)

        def get_client(*args):
            """ Tricky way to return necessary node """
            if args and args[6] == 'slave-01':
                return self.ipmiclient1
            elif args and args[6] == 'slave-02':
                return self.ipmiclient2

        self.ipmiclient_mock.side_effect = get_client

    def test_db(self):
        """ Tets DB """
        node = self.env.get_node(name='slave-01')
        assert(node.ipmi_user) == 'user1'
        assert (node.ipmi_password) == 'pass1'
        assert (node.ipmi_previlegies) == 'OPERATOR'
        assert (node.ipmi_host) == 'ipmi-1.host.address.net'
        assert (node.ipmi_lan_interface) == 'lanplus'
        assert (node.ipmi_port) == 623

        node2 = self.env.get_node(name='slave-02')
        assert (node2.ipmi_user) == 'user2'
        assert (node2.ipmi_password) == 'pass2'
        assert (node2.ipmi_previlegies) == 'OPERATOR'
        assert (node2.ipmi_host) == 'ipmi-2.host.address.net'
        assert (node2.ipmi_lan_interface) == 'lanplus'
        assert (node2.ipmi_port) == 623

    def test_life_cycle(self):
        """ Test lifecycle """
        self.env.define()

        self.env.start()
        assert self.ipmiclient_mock.call_count == 2
        self.ipmiclient_mock.assert_any_call(
            'user1', 'pass1', 'ipmi-1.host.address.net', 'OPERATOR',
            'lanplus', 623, 'slave-01')
        self.ipmiclient_mock.assert_any_call(
            'user2', 'pass2', 'ipmi-2.host.address.net', 'OPERATOR',
            'lanplus', 623, 'slave-02')
        self.ipmiclient1.power_on.assert_called_once_with()

        self.env.destroy()
        self.ipmiclient1.power_off.assert_called_once_with()

        self.env.erase()
        self.ipmiclient1.power_off.assert_called_once_with()
