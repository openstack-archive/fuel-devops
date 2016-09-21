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

from devops.models.node_ext import fuel_master


class NodeExtension(fuel_master.NodeExtension):
    """Extension for Fuel 5.1"""

    def get_kernel_cmd(self, boot_from='cdrom', iface='enp0s3',
                       wait_for_external_config='yes'):
        return (
            '<Wait>\n'
            '<Wait>\n'
            '<Wait>\n'
            '<Esc><Enter>\n'
            '<Wait>\n'
            'vmlinuz initrd=initrd.img ks=cdrom:/ks.cfg\n'
            ' ip={ip}\n'
            ' netmask={mask}\n'
            ' gw={gw}\n'
            ' dns1={nameserver}\n'
            ' hostname={hostname}\n'
            ' dhcp_interface=' + iface + '\n'
            ' <Enter>\n')

    def get_deploy_check_cmd(self):
        return ("grep 'Fuel node deployment complete' "
                "'/var/log/puppet/bootstrap_admin_node.log'")
