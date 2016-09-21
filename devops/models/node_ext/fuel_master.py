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

from django.conf import settings

from devops import error
from devops.helpers import helpers


class NodeExtension(object):
    """Extension for the latest Fuel development build"""

    def __init__(self, node):
        self.node = node

    def _start_setup(self):
        if self.node.kernel_cmd is None:
            raise error.DevopsError('kernel_cmd is None')

        self.node.start()
        self.send_kernel_keys(self.node.kernel_cmd)

    def send_kernel_keys(self, kernel_cmd):
        """Provide variables data to kernel cmd format template"""

        ip = self.node.get_ip_address_by_network_name(
            settings.SSH_CREDENTIALS['admin_network'])
        master_iface = self.node.get_interface_by_network_name(
            settings.SSH_CREDENTIALS['admin_network'])
        admin_ap = master_iface.l2_network_device.address_pool

        result_kernel_cmd = kernel_cmd.format(
            ip=ip,
            mask=admin_ap.ip_network.netmask,
            gw=admin_ap.gateway,
            hostname=settings.DEFAULT_MASTER_FQDN,
            nameserver=settings.DEFAULT_DNS,
        )
        self.node.send_keys(result_kernel_cmd)

    def bootstrap_and_wait(self):
        if self.node.kernel_cmd is None:
            self.node.kernel_cmd = self.get_kernel_cmd()
            self.node.save()
        self._start_setup()
        ip = self.node.get_ip_address_by_network_name(
            settings.SSH_CREDENTIALS['admin_network'])
        helpers.wait_tcp(
            host=ip, port=self.node.ssh_port,
            timeout=self.node.bootstrap_timeout)

    def deploy_wait(self):
        ip = self.node.get_ip_address_by_network_name(
            settings.SSH_CREDENTIALS['admin_network'])
        if self.node.deploy_check_cmd is None:
            self.node.deploy_check_cmd = self.get_deploy_check_cmd()
            self.node.save()
            helpers.wait_ssh_cmd(
                host=ip,
                port=self.node.ssh_port,
                check_cmd=self.node.deploy_check_cmd,
                username=settings.SSH_CREDENTIALS['login'],
                password=settings.SSH_CREDENTIALS['password'],
                timeout=self.node.deploy_timeout)

    def get_kernel_cmd(self, boot_from='cdrom', iface='enp0s3',
                       wait_for_external_config='yes'):
        if boot_from == 'usb':
            keys = (
                '<Wait>\n'
                '<Wait>\n'
                '<Wait>\n'
                '<F12>\n'
                '2\n'
            )
        else:  # cdrom is default
            keys = (
                '<Wait>\n'
                '<Wait>\n'
                '<Wait>\n'
            )

        keys += (
            '<Esc>\n'
            '<Wait>\n'
            'vmlinuz initrd=initrd.img'
            ' inst.ks=cdrom:LABEL=OpenStack_Fuel:/ks.cfg'
            ' inst.repo=cdrom:LABEL=OpenStack_Fuel:/'
            ' ip={ip}::{gw}:{mask}:{hostname}'
            ':' + iface + ':off::: nameserver={nameserver}'
            ' showmenu=no\n'
            ' wait_for_external_config=' + wait_for_external_config + '\n'
            ' build_images=0\n'
            ' <Enter>\n'
        )
        return keys

    def get_deploy_check_cmd(self):
        return 'timeout 15 fuel-utils check_all'
