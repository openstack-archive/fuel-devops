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

from ipaddr import IPNetwork
import ipaddr

from devops.helpers.helpers import SSHClient
# from devops.models import DiskDevice
from devops.models import Environment
from devops.models import Interface
from devops.models import Network
from devops.models import Node
# from devops.models import BareMetalNode
# from devops.models import Volume
# import os
from devops.helpers import node_manager


def one():
    environment = Environment.create('test_baremetal')

    environment.driver.iface_define(name='em2')
    environment.driver.iface_bridge_define(bridge_name='fbr-admin',
                                           parent_name='em2')
    environment.driver.iface_create('fbr-admin')
    admin_net = Network.network_create(
        environment=environment, name='admin',
        ip_network='10.109.0.0/24',
        forward='bridge', target_dev="fbr-admin")

    environment.driver.iface_define(name='em2', vlanid=1201)
    environment.driver.iface_bridge_define(bridge_name='fbr-public',
                                           parent_name='em2',
                                           vlanid=1201)
    environment.driver.iface_create('fbr-public')
    public_net = Network.network_create(
        environment=environment, name='public',
        ip_network='10.109.1.0/24',
        forward='bridge', target_dev="fbr-public")


    environment.driver.iface_define(name='em2', vlanid=1202)
    environment.driver.iface_bridge_define(bridge_name='fbr-mgmt',
                                           parent_name='em2',
                                           vlanid=1202)
    environment.driver.iface_create('fbr-mgmt')
    management_net = Network.network_create(
        environment=environment, name='management',
        ip_network='10.109.2.0/24',
        forward='bridge', target_dev="fbr-mgmt")


    environment.driver.iface_define(name='em2', vlanid=1203)
    environment.driver.iface_bridge_define(bridge_name='fbr-private',
                                           parent_name='em2',
                                           vlanid=1203)
    environment.driver.iface_create('fbr-private')
    private_net = Network.network_create(
        environment=environment, name='private',
        ip_network='10.109.3.0/24',
        forward='bridge', target_dev="fbr-private")


    environment.driver.iface_define(name='em2', vlanid=1204)
    environment.driver.iface_bridge_define(bridge_name='fbr-storage',
                                           parent_name='em2',
                                           vlanid=1204)
    environment.driver.iface_create('fbr-storage')
    storage_net = Network.network_create(
        environment=environment, name='storage',
        ip_network='10.109.4.0/24',
        forward='bridge', target_dev="fbr-storage")

    iso_path = ('/home/iso/fuel-7.0-104-2015-07-28_21-24-26.iso')
    networks = [
        admin_net,
        public_net,
        management_net,
        private_net,
        storage_net
        ]

    iso_path = "/home/iso/fuel-version.iso"
    admin_node = environment.describe_admin_node(name="admin",
                                                 vcpu=2,
                                                 networks=networks,
                                                 memory=2048,
                                                 iso_path=iso_path)


    # admin_node = environment.add_node(name='admin', vcpu=2, memory=2048,
    #                                   boot=['hd', 'network'])
    # disknames_capacity = {
    #     'system': 50 * 1024 ** 3,
    #     # 'cinder': 50 * 1024 ** 3,
    #     # 'swift': 50 * 1024 ** 3
    # }
    # admin_node.attach_disks(
    #     disknames_capacity=disknames_capacity,
    #     force_define=False)
    # DiskDevice.node_attach_volume(
    #     admin_node,
    #     Volume.volume_get_predefined(
    #         '/home/dtyzhnenko/Downloads/fuel-iso/fuel-7.0-98-2015-07-27_09-24-22.iso'),
    #     device='cdrom', bus='sata')
    # admin_node.attach_to_networks()
    iso_path = ('/home/dtyzhnenko/Downloads/fuel-iso/'
                'fuel-7.0-98-2015-07-27_09-24-22.iso')
    networks = 'admin,public,management,private,storage'.split(',')
    environment.describe_admin_node(name="admin",
                                    vcpu=2,
                                    networks=networks,
                                    memory=2048,
                                    iso_path=iso_path)

    i_user, i_pass = "ipmi-user", "ipmi-password"
    # first ipmi host
    s01 = environment.add_node(name="slave-01", memory=0, vcpu=0, role='slave',
                               node_type='real',
                               ipmi_uri="ipmi://{u}:{p}@127.0.0.2/".format(
                                    u=i_user,
                                    p=i_pass
                               ))

    # second ipmi host
    s02 = environment.add_node(name="slave-02", memory=0, vcpu=0, role='slave',
                               node_type='real',
                               ipmi_uri="ipmi://{u}:{p}@127.0.0.3/".format(
                                    u=i_user,
                                    p=i_pass
                               ))

    # third ipmi host
    s03 = environment.add_node(name="slave-03", memory=0, vcpu=0, role='slave',
                               node_type='real',
                               ipmi_uri="ipmi://{u}:{p}@127.0.0.4/".format(
                                    u=i_user,
                                    p=i_pass
                               ))

    admin_node = environment.get_node(name='admin')
    node_manager.admin_change_config(admin_node)
    node_manager.admin_wait_bootstrap(3000, environment)

    # Start slave nodes
    s01.restart()
    s02.restart()
    s03.restart()


if __name__ == '__main__':
    one()
