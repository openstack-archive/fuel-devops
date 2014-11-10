#    Copyright 2014 Mirantis, Inc.
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

import ipaddr


def one():
    environment = environment.environment_create('test_env8_bridged_network')
    internal_pool = environment.create_network_pool(
        networks=[ipaddr.IPNetwork('10.208.0.0/16')], prefix=24
    )
    private_pool = environment.create_network_pool(
        networks=[ipaddr.IPNetwork('10.208.0.0/16')], prefix=24
    )
    external_pool = environment.create_network_pool(
        networks=[ipaddr.IPNetwork('172.18.95.0/24')], prefix=27
    )
    environment.driver.iface_define(name='dummy0', vlanid=300)
    environment.driver.iface_define(name='dummy0', vlanid=301)
    environment.driver.iface_define(name='dummy0', vlanid=302)
    environment.driver.iface_create('dummy0.300')
    environment.driver.iface_create('dummy0.301')
    environment.driver.iface_create('dummy0.302')

    environment.driver.iface_bridge_define(bridge_name='test-br-int',
                                           parent_name='dummy0',
                                           vlanid=300)
    environment.driver.iface_bridge_define(bridge_name='test-br-pri',
                                           parent_name='dummy0',
                                           vlanid=301)
    environment.driver.iface_bridge_define(bridge_name='test-br-ext',
                                           parent_name='dummy0',
                                           vlanid=302)
    environment.driver.iface_create('test-br-int')
    environment.driver.iface_create('test-br-pri')
    environment.driver.iface_create('test-br-ext')

    internal = environment.network_create(
        environment=environment, name='internal', pool=internal_pool,
        forward='bridge', target_dev="test-br-int")
    external = environment.network_create(
        environment=environment, name='external', pool=external_pool,
        forward='bridge', target_dev="test-br-pri")
    private = environment.network_create(
        environment=environment, name='private', pool=private_pool,
        forward='bridge', target_dev="test-br-ext")
    for i in range(0, 5):
        node = environment.node_create(
            name='test_node' + str(i),
            environment=environment)
        environment.interface_create(node=node, network=internal)
        environment.interface_create(node=node, network=external)
        environment.interface_create(node=node, network=private)
        system_volume = environment.volume_create(
            name='{0}-system'.format(node.name),
            capacity=25000,
            environment=environment)
        ceph_volume = environment.volume_create(
            name='{0}-ceph'.format(node.name),
            capacity=25000,
            environment=environment)
        environment.node_attach_volume(node=node, volume=system_volume)
        environment.node_attach_volume(node=node, volume=ceph_volume)

    environment.define()
    environment.start()


if __name__ == '__main__':
    from devops.environment import environment

    one(environment())
