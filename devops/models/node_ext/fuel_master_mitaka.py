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


class NodeExtension(object):
    """Extension for Fuel Mitaka"""

    def __init__(self, node):
        self.node = node

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
