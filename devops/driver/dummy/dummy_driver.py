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

"""
This module shows how to implement a new driver for fuel-devops.

To be able to load this driver, you need to put the path to the template file
in section group['driver']['name']. This module should contain 4 major classes:
Driver, L2NetworkDevice, Volume, Node.
"""

from __future__ import print_function

from devops.models import base
from devops.models import driver
from devops.models import network
from devops.models import node
from devops.models import volume


class DummyDriver(driver.Driver):
    """Example of driver implementation

    Note: This class is imported as Driver at .__init__.py

    This class should contain parameters specified in template
    group['driver']['params']

    yaml example:

    groups:
    - name: rack-01
      driver:
        name: devops.driver.dummy.dummy_driver
        params:
          dummy_parameter: 15
          choice_parameter: two
          nested:
            parameter: abc

    """

    # example parameters
    dummy_parameter = base.ParamField(default=10)
    choice_parameter = base.ParamField(default='one',
                                       choices=('one', 'two', 'three'))
    nested = base.ParamMultiField(
        parameter=base.ParamField()
    )

    def get_allocated_networks(self):
        """This methods return list of already allocated networks.

        implement it if your driver knows which network pools
        are already taken by the driver
        """
        # example format
        return ['192.168.0.0/24', '192.168.1.0/24']


class DummyL2NetworkDevice(network.L2NetworkDevice):
    """Example implementation of l2 network device.

    Note: This class is imported as L2NetworkDevice at .__init__.py

    L2NetworkDevice represents node/device which acts like switch or router

    yaml example:

    l2_network_devices:
      admin:
        address_pool: fuelweb_admin-pool01
        dhcp: false
        other: abcd

      public:
        address_pool: public-pool01
        dhcp: false
        other: efgh

    """

    # example parameter
    dhcp = base.ParamField(default=False)
    other = base.ParamField(default='')

    def define(self):
        """Define

        Define method is called one time after environment successfully
        saved from template to database. It should contain something to prepare
        an instance of L2NetworkDevice before start
        """

        print('Do something before define')

        # driver instance is available from property self.driver
        # so you can use any parameters defined in driver
        print(self.driver)
        print(self.driver.dummy_parameter)
        print(self.driver.nested.parameter)

        # parameters of L2NetworkDevice
        print(self.dhcp)
        print(self.other)

        # name of L2NetworkDevice
        print(self.name)

        # associated adress pool
        print(self.address_pool)
        # and network
        print(self.address_pool.ip_network)

        super(DummyL2NetworkDevice, self).define()
        print('Do something after define')

    def start(self):
        """Start

        Start method is called every time you want to boot up previsously
        saved and defined l2 network device
        """

        print('implementation of start')

    def destroy(self):
        """Destroy

        Destroy method is called every time you want to power off
        previsously started l2 network device
        """
        print('implementation of destroy')

    def erase(self):
        """Erase

        Erase method is called one time when you want remove existing
        l2 network device
        """
        super(DummyL2NetworkDevice, self).erase()
        print('Do something after erase')


class DummyVolume(volume.Volume):
    """Example implementation of volume

    Note: This class is imported as Volume at .__init__.py

    Volume is image or disk which should be mounted to a specific Node
    """

    # example parameter
    size = base.ParamField(default=1024)

    def define(self):
        """Define

        Define method is called one time after environment successfully
        saved from template to database. It should contain something to prepare
        an instance of Volume before usage in Node class
        """
        # driver instance is available from property self.driver
        # so you can use any parameters defined in driver
        print(self.driver)
        print(self.driver.dummy_parameter)

        print('Do something before define')
        super(DummyVolume, self).define()
        print('Do something after define')

    def erase(self):
        """Erase

        Erase method is called one time when you want remove existing
        volume
        """
        print('Do something before erase')
        super(DummyVolume, self).erase()
        print('Do something after erase')


class DummyNode(node.Node):
    """Example implementation of node

    Note: This class is imported as Node at .__init__.py

    Node is a server which will be used for deloying of openstack depending on
    node role

    yaml example:

    nodes:
    - name: slave
      role: fuel_slave
      params:
        cpu: 2
        memory: 3072
        boot:
          - hd
          - cdrom
        volumes:
         - name: system
           size: 75
           format: qcow2
        interfaces:
         - label: eth0
           l2_network_device: admin
           interface_model: e1000
        network_config:
          eth0:
            networks:
             - fuelweb_admin
    """

    cpu = base.ParamField(default=1)
    memory = base.ParamField(default=1024)
    boot = base.ParamField(default=['network', 'cdrom', 'hd'])

    def define(self):
        """Define

        Define method is called one time after environment successfully
        saved from template to database. It should contain something to
        prepare an instance of Node before start
        """

        # driver instance is available from property self.driver
        print(self.driver)

        # node parameters
        print(self.cpu)
        print(self.memory)
        print(self.boot)

        # list of disk devices
        print(self.disk_devices)

        # list of network interfaces
        print(self.interfaces)

        print('Do something before define')
        super(DummyNode, self).define()
        print('Do something after define')

    def start(self):
        """Start method is called every time you want to boot up node"""
        print('implementation of start')

    def destroy(self):
        """Destroy

        Destroy method is called every time you want to power off
        previsously started node
        """
        print('implementation of destroy')

    def erase(self):
        """Erase

        Erase method is called one time when you want remove existing
        node
        """
        print('Do something before erase')
        super(DummyNode, self).erase()
        print('Do something after erase')
