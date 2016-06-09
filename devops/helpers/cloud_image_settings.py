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
import subprocess

from devops import logger


def generate_cloud_image_settings(cloud_image_settings_path, admin_network,
                                  interface_name, admin_ip, admin_netmask,
                                  gateway, dns, dns_ext,
                                  hostname, user, password):

    # create dir for meta_data, user_data and cloud_ISO
    dir_path = os.path.dirname(cloud_image_settings_path)

    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    meta_data_path = os.path.join(dir_path,
                                  "meta-data")
    user_data_path = os.path.join(dir_path,
                                  "user-data")

    # create meta_data and user_data

    meta_data_context = {
        "interface_name": interface_name,
        "address": admin_ip,
        "network": admin_network,
        "netmask": admin_netmask,
        "gateway": gateway,
        "dns": dns,
        "dns_ext": dns_ext,
        "hostname": hostname
    }

    meta_data_content = ("instance-id: iid-local1\n"
                         "network-interfaces: |\n"
                         " auto {interface_name}\n"
                         " iface {interface_name} inet static\n"
                         " address {address}\n"
                         " network {network}\n"
                         " netmask {netmask}\n"
                         " gateway {gateway}\n"
                         " dns-nameservers {dns} {dns_ext}\n"
                         "local-hostname: {hostname}")

    logger.debug("meta_data contains next data: \n{}".format(
        meta_data_content.format(**meta_data_context)))

    with open(meta_data_path, 'w') as f:
        f.write(meta_data_content.format(**meta_data_context))

    user_data_context = {
        "interface_name": interface_name,
        "gateway": gateway,
        "user": user,
        "password": password
    }

    user_data_content = ("\n#cloud-config\n"
                         "ssh_pwauth: True\n"
                         "chpasswd:\n"
                         " list: |\n"
                         "  {user}:{password}\n"
                         " expire: False \n\n"
                         "runcmd:\n"
                         " - sudo ifup {interface_name}\n"
                         " - sudo sed -i -e '/^PermitRootLogin/s/^"
                         ".*$/PermitRootLogin yes/' /etc/ssh/sshd_config\n"
                         " - sudo service ssh restart\n"
                         " - sudo route add default gw "
                         "{gateway} {interface_name}")

    logger.debug("user_data contains next data: \n{}".format(
        user_data_content.format(**user_data_context)))

    with open(user_data_path, 'w') as f:
        f.write(user_data_content.format(**user_data_context))

    # Generate cloud_ISO
    cmd = "genisoimage -output {} " \
          "-volid cidata -joliet " \
          "-rock {} {}".format(cloud_image_settings_path,
                               user_data_path,
                               meta_data_path)

    subprocess.check_call(cmd, shell=True)
