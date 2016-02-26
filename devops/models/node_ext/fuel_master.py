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

from devops.settings import DEFAULT_DNS
from devops.settings import DEFAULT_MASTER_FQDN
from devops.settings import SSH_CREDENTIALS


class NodeExtension(object):

    def __init__(self, node):
        self.node = node

    def _send_keys(self, kernel_cmd):
        """Provide virables data to kernel cmd format template"""

        master_iface = self.node.get_interface_by_nailgun_network_name(
            SSH_CREDENTIALS['admin_network'])
        admin_ip_net = master_iface.l2_network_device.address_pool.ip_network

        params = {
            'repo': 'hd:LABEL=Mirantis_Fuel:/',  # only required for USB boot
            'ip': master_iface.address_set.first().ip_address,
            'mask': admin_ip_net.netmask,
            'gw': admin_ip_net[1],
            'hostname': DEFAULT_MASTER_FQDN,
            'nat_interface': '',
            'dns1': DEFAULT_DNS,
            'showmenu': 'no',
            'wait_for_external_config': 'yes',
            'build_images': '0',
            'iface': 'enp0s3',
        }

        result_kernel_cmd = kernel_cmd.format(**params)
        self.node.send_keys(result_kernel_cmd)

    def get_deploy_check_cmd(self):
        return 'timeout 15 fuel-utils check_all'
