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

from netaddr import IPNetwork

from devops.helpers.ssh_client import SSHClient
from devops.models import DiskDevice
from devops.models import Environment
from devops.models import Interface
from devops.models import Network
from devops.models import Node
from devops.models import Volume


def one():
    environment = Environment.create('test_env7')
    internal_pool = Network.create_network_pool(
        networks=[IPNetwork('10.108.0.0/16')], prefix=24
    )
    private_pool = Network.create_network_pool(
        networks=[IPNetwork('10.108.0.0/16')], prefix=24
    )
    external_pool = Network.create_network_pool(
        networks=[IPNetwork('172.18.95.0/24')], prefix=27
    )
    internal = Network.network_create(
        environment=environment, name='internal', pool=internal_pool)
    external = Network.network_create(
        environment=environment, name='external', pool=external_pool,
        forward='nat')
    private = Network.network_create(
        environment=environment, name='private', pool=private_pool)
    for i in range(0, 15):
        node = Node.node_create(
            name='test_node' + str(i),
            environment=environment)
        Interface.interface_create(node=node, network=internal)
        Interface.interface_create(node=node, network=external)
        Interface.interface_create(node=node, network=private)
        volume = Volume.volume_get_predefined(
            '/var/lib/libvirt/images/centos63-cobbler-base.qcow2')
        v3 = Volume.volume_create_child(
            'test_vp895' + str(i),
            backing_store=volume,
            environment=environment)
        v4 = Volume.volume_create_child(
            'test_vp896' + str(i),
            backing_store=volume,
            environment=environment)
        DiskDevice.node_attach_volume(node=node, volume=v3)
        DiskDevice.node_attach_volume(node, v4)
    environment.define()
    environment.start()
    remotes = []
    for node in environment.get_nodes():
        node.await('internal')
        node.remote('internal', 'root', 'r00tme').check_stderr(
            'ls -la', verbose=True)
        remotes.append(node.remote('internal', 'root', 'r00tme'))
    SSHClient.execute_together(remotes, 'ls -la')


if __name__ == '__main__':
    one()
