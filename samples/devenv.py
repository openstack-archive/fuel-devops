#!/usr/bin/env python

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

import argparse

import ipaddr


env_name = 'test-env7'
node_name = 'tempest-%s' % (env_name)
template_volume = '/media/build/libvirt_default/vm_tempest_template.img'


def add_node(manager):
    try:
        environment = manager.environment_get(env_name)
    except:
        exit(1)

    try:
        tempest_node = manager.node_create(name=node_name,
                                           environment=environment,
                                           boot=['hd'])
    except:
        # tempest_node = environment.node_by_name(name=node_name)
        exit(2)

    # connect to external network via host bridge
    # def network_create(
    #     self, name, environment=None, ip_network=None, pool=None,
    #     has_dhcp_server=True, has_pxe_server=False,
    #     forward='nat'
    # ):
    # forward = choices(
    #     'nat', 'route', 'bridge', 'private', 'vepa',
    #     'passthrough', 'hostdev', null=True)
    try:
        br_net = environment.network_by_name('br0')
    except:
        br_net = manager.network_create(environment=environment,
                                        name='br0',  # name of the host bridge
                                                     # to connect
                                        ip_network=True,
                                        forward='hostdev')
    # TODO: implement create_or_get to host networks

    # def interface_create(self, network, node, type='network',
    #                      mac_address=None, model='virtio'):
    manager.interface_create(node=tempest_node,
                             network=br_net,
                             type='bridge')

    # connect to internal network
    try:
        env_net = environment.network_by_name('internal')
        manager.interface_create(node=tempest_node, network=env_net)
    except:
        exit(3)

    print(env_net.next_ip())

    # create and connect volume
    vol_tpl = manager.volume_get_predefined(template_volume)
    vol_base = manager.volume_create_child(node_name + 'test_vol',
                                           backing_store=vol_tpl,
                                           environment=environment)
    manager.node_attach_volume(node=tempest_node, volume=vol_base)

    env_net.save()
    vol_base.define()
    tempest_node.define()
    tempest_node.start()
    exit()

    remotes = []
    tempest_node.await(br_net.name)

    hostname = ('%s-%s' % (tempest_node.name, env_name)).replace('_', '-')
    print(hostname)
    tempest_node.remote(
        env_net.name,
        'jenkins',
        'jenkins').check_stderr(
            'sudo hostname {}; '
            'ifconfig eth0 | grep "inet addr";'.format(hostname),
            verbose=True)
    remotes.append(tempest_node.remote(env_net.name, 'jenkins', 'jenkins'))


def create_env(manager):
    environment = manager.environment_create(env_name)
    internal_pool = manager.create_network_pool(
        networks=[ipaddr.IPNetwork('10.108.0.0/16')], prefix=24
    )
    private_pool = manager.create_network_pool(
        networks=[ipaddr.IPNetwork('10.109.0.0/16')], prefix=24
    )
    external_pool = manager.create_network_pool(
        networks=[ipaddr.IPNetwork('10.110.0.0/16')], prefix=27
    )
    internal = manager.network_create(
        environment=environment, name='internal', pool=internal_pool)
    external = manager.network_create(
        environment=environment, name='external', pool=external_pool,
        forward='nat')
    private = manager.network_create(
        environment=environment, name='private', pool=private_pool)
    for i in range(0, 2):
        node = manager.node_create(name='test_node' + str(i),
                                   environment=environment,
                                   boot=['hd'])
        manager.interface_create(node=node, network=internal)
        manager.interface_create(node=node, network=external)
        manager.interface_create(node=node, network=private)
        volume = manager.volume_get_predefined(
            '/media/build/libvirt_default/vm_ubuntu_initial.img')
        v3 = manager.volume_create_child('test_vp895' + str(i),
                                         backing_store=volume,
                                         environment=environment)
        # v4 = manager.volume_create_child('test_vp896' + str(i),
        #                                  backing_store=volume,
        #                                  environment=environment)
        manager.node_attach_volume(node=node, volume=v3)
        # manager.node_attach_volume(node, v4)
    environment.define()
    environment.start()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create environment or add'
                                     'VM to environment created via devops.')
    parser.add_argument('command',
                        choices=['create-env', 'add-node'],
                        help='command')
    parser.add_argument('-e', '--env-name',
                        help='name of the environment to create')
    parser.add_argument('-n', '--name',
                        help='name of the VM to create')
    args = parser.parse_args()
    env_name = args.env_name
    node_name = args.name

    from devops.manager import Manager
    if args.command == 'create-env':
        create_env(Manager())
    elif args.command == 'add-node':
        add_node(Manager())
