#    Copyright 2013 Mirantis, Inc.
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
from devops.helpers.helpers import SSHClient


def one(manager):
    environment = manager.environment_create('cdrom')
    internal_pool = manager.create_network_pool(
        networks=[ipaddr.IPNetwork('10.108.0.0/16')], prefix=24
    )
    private_pool = manager.create_network_pool(
        networks=[ipaddr.IPNetwork('10.108.0.0/16')], prefix=24
    )
    external_pool = manager.create_network_pool(
        networks=[ipaddr.IPNetwork('172.18.95.0/24')], prefix=27
    )
    internal = manager.network_create(
        environment=environment, name='internal', pool=internal_pool)
    external = manager.network_create(
        environment=environment, name='external', pool=external_pool,
        forward='nat')
    private = manager.network_create(
        environment=environment, name='private', pool=private_pool)
    for i in range(1, 2):
        node = manager.node_create(
            name='test_node' + str(i), environment=environment)
        manager.interface_create(node=node, network=internal)
        manager.interface_create(node=node, network=external)
        manager.interface_create(node=node, network=private)
        volume = manager.volume_get_predefined(
            '/var/lib/libvirt/images/centos63-cobbler-base.qcow2')
        v3 = manager.volume_create_child(
            'test_vp895' + str(i), backing_store=volume,
            environment=environment)
        v4 = manager.volume_create_child(
            'test_vp896' + str(i), backing_store=volume,
            environment=environment)
        manager.node_attach_volume(node=node, volume=v3)
        manager.node_attach_volume(node, v4)
        manager.node_attach_volume(
            node,
            manager.volume_get_predefined(
                '/var/lib/libvirt/images/fuel-centos-6.3-x86_64.iso'),
            device='cdrom', bus='sata')
    environment.define()
    environment.start()
    remotes = []
    for node in environment.nodes:
        node.await('internal')
        node.remote('internal', 'root', 'r00tme').check_stderr(
            'ls -la', verbose=True)
        remotes.append(node.remote('internal', 'root', 'r00tme'))
    SSHClient.execute_together(remotes, 'ls -la')


if __name__ == '__main__':
    from devops.manager import Manager

    one(Manager())
