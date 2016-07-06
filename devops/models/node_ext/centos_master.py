
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

#import os
#import shutil

#from devops.helpers.cloud_image_settings import generate_cloud_image_settings
from devops.helpers.helpers import wait_tcp
from devops import logger
from devops import settings


class NodeExtension(object):
    """Extension for Centos Master node"""

    def __init__(self, node):
        self.node = node

    def bootstrap_and_wait(self):
        self.node.start()
        ip = self.node.get_ip_address_by_network_name(
            settings.SSH_CREDENTIALS['admin_network'])
        wait_tcp(host=ip, port=self.node.ssh_port,
                 timeout=self.node.bootstrap_timeout,
                 timeout_msg='Failed to bootstrap centos master')
        logger.info('Centos cloud image bootstrap complete')

    def deploy_wait(self):
        # Do nothing
        logger.warning('Fuel is going to be installed manually in tests')

    def get_kernel_cmd(self, **kwargs):
        return None

    def pre_define(self):

        if self.node.cloud_init_volume_name is None:
            self.node.cloud_init_volume_name = 'iso'

        if self.node.cloud_init_iface_up is None:
            interface = self.node.get_interface_by_network_name(
                settings.SSH_CREDENTIALS['admin_network'])
            self.node.cloud_init_iface_up = interface.label

        self.node.save()

        volume = self.node.get_volume(name=self.node.cloud_init_volume_name)

        if volume.cloudinit_meta_data is None:
            volume.cloudinit_meta_data = (
                "instance-id: iid-local1\n"
                "network-interfaces: |\n"
                " auto {interface_name}\n"
                " iface {interface_name} inet static\n"
                " address {address}\n"
                " network {network}\n"
                " netmask {netmask}\n"
                " gateway {gateway}\n" +
                " dns-nameservers {dns}\n"
                "local-hostname: {hostname}".format(
                    dns=settings.DEFAULT_DNS,
                    hostname=settings.DEFAULT_MASTER_FQDN))

        if volume.cloudinit_meta_data is None:
            volume.cloudinit_user_data = (
                "\n#cloud-config\n"
                "ssh_pwauth: True\n"
                "chpasswd:\n"
                " list: |\n" +
                "  {user}:{password}\n".format(
                    user=settings.SSH_CREDENTIALS['login'],
                    password=settings.SSH_CREDENTIALS['password']
                    ) +
                " expire: False \n\n"
                "runcmd:\n"
                " - sudo ifup {interface_name}\n"
                " - sudo sed -i -e '/^PermitRootLogin/s/^"
                ".*$/PermitRootLogin yes/' /etc/ssh/sshd_config\n"
                " - sudo service ssh restart\n"
                " - sudo route add default gw "
                "{gateway} {interface_name}")
        volume.save()
