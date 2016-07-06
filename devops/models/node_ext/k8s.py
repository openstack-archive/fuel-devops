
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

import os
import shutil

from devops.helpers.cloud_image_settings import generate_cloud_image_settings
from devops import settings


class NodeExtension(object):
    """Extension for node with cloud-init"""

    def __init__(self, node):
        self.node = node

    def post_define(self):
        """Builds setting iso to send basic configuration for cloud image"""

        if self.node.cloud_init_volume_name is None:
            return
        volume = self.node.get_volume(name=self.node.cloud_init_volume_name)

        interface = self.node.interface_set.get(
            label=self.node.cloud_init_iface_up)
        admin_ip = self.node.get_ip_address_by_network_name(
            name=None, interface=interface)

        env_name = self.node.group.environment.name
        dir_path = os.path.join(settings.CLOUD_IMAGE_DIR,env_name)
        cloud_image_settings_path = os.path.join(
            dir_path, 'cloud_settings.iso')
        meta_data_path = os.path.join(dir_path, "meta-data")
        user_data_path = os.path.join(dir_path, "user-data")

        interface_name = interface.label
        user = settings.SSH_CREDENTIALS['login']
        password = settings.SSH_CREDENTIALS['password']
        admin_ap = interface.l2_network_device.address_pool
        gateway = str(admin_ap.gateway)
        admin_netmask = str(admin_ap.ip_network.netmask)
        admin_network = str(admin_ap.ip_network)
        dns = settings.DEFAULT_DNS
        dns_ext = dns
        hostname = self.node.name

        generate_cloud_image_settings(
            cloud_image_settings_path=cloud_image_settings_path,
            meta_data_path=meta_data_path,
            user_data_path=user_data_path,
            admin_network=admin_network,
            interface_name=interface_name,
            admin_ip=admin_ip,
            admin_netmask=admin_netmask,
            gateway=gateway,
            dns=dns,
            dns_ext=dns_ext,
            hostname=hostname,
            user=user,
            password=password,
            meta_data_content=volume.cloudinit_meta_data,
            user_data_content=volume.cloudinit_user_data,
        )

        volume.upload(cloud_image_settings_path)

        # Clear temporary files
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
