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

from functools import partial

import yaml
from django.conf import settings

from devops.helpers.helpers import tcp_ping
from devops.helpers.helpers import wait
from devops.helpers.helpers import create_empty_file
from devops.helpers.helpers import SSHClient
from devops import logger


class NodeExtension(object):

    def __init__(self, node):
        self.node = node

    def default_setup(self):
        self.start_node_with_boot_menu()
        self.wait_for_ssh()
        conf = self.get_config()
        self.config_update_router(conf)
        self.save_config(conf)
        self.wait_deploy_end()

    def _get_keys(self, iso_connect_as='cdrom', master_is_centos7=False):
        if master_is_centos7:
            if iso_connect_as == 'usb':
                return (
                    "<Wait>\n"  # USB boot uses boot_menu=yes for master node
                    "<F12>\n"
                    "2\n"
                    "<Esc><Enter>\n"
                    "<Wait>\n"
                    "vmlinuz initrd=initrd.img ks={ks}\n"
                    " repo={repo}\n"
                    " ip={ip}::{gw}:{mask}:{hostname}"
                    ":{iface}:off::: dns1={dns1}"
                    " showmenu={showmenu}\n"
                    " wait_for_external_config={wait_for_external_config}\n"
                    " build_images={build_images}\n"
                    " <Enter>\n"
                )
            else:  # cdrom case is default
                return (
                    "<Wait>\n"
                    "<Wait>\n"
                    "<Wait>\n"
                    "<Esc>\n"
                    "<Wait>\n"
                    "vmlinuz initrd=initrd.img ks={ks}\n"
                    " ip={ip}::{gw}:{mask}:{hostname}"
                    ":{iface}:off::: dns1={dns1}"
                    " showmenu={showmenu}\n"
                    " wait_for_external_config={wait_for_external_config}\n"
                    " build_images={build_images}\n"
                    " <Enter>\n"
                )
        if iso_connect_as == 'usb':
            return (
                "<Wait>\n"  # USB boot uses boot_menu=yes for master node
                "<F12>\n"
                "2\n"
                "<Esc><Enter>\n"
                "<Wait>\n"
                "vmlinuz initrd=initrd.img ks={ks}\n"
                " repo={repo}\n"
                " ip={ip}\n"
                " netmask={mask}\n"
                " gw={gw}\n"
                " dns1={dns1}\n"
                " hostname={hostname}\n"
                " dhcp_interface={nat_interface}\n"
                " showmenu={showmenu}\n"
                " wait_for_external_config={wait_for_external_config}\n"
                " build_images={build_images}\n"
                " <Enter>\n"
            )
        else:  # cdrom case is default
            return (
                "<Wait>\n"
                "<Wait>\n"
                "<Wait>\n"
                "<Esc>\n"
                "<Wait>\n"
                "vmlinuz initrd=initrd.img ks={ks}\n"
                " ip={ip}\n"
                " netmask={mask}\n"
                " gw={gw}\n"
                " dns1={dns1}\n"
                " hostname={hostname}\n"
                " dhcp_interface={nat_interface}\n"
                " showmenu={showmenu}\n"
                " wait_for_external_config={wait_for_external_config}\n"
                " build_images={build_images}\n"
                " <Enter>\n"
            )

    def start_node_with_boot_menu(
            self, keys=None,
            build_images=False,
            master_is_centos7=False,
            iso_connect_as='cdrom',
            hostname=settings.DEFAULT_MASTER_FQDN,
            admin_net=settings.SSH_CREDENTIALS['admin_network'],
            nat_interface='',
            dns=settings.DEFAULT_DNS,
            iface='enp0s3'):

        if keys is None:
            keys = self._get_keys(iso_connect_as=iso_connect_as,
                                  master_is_centos7=master_is_centos7)

        master_iface = self.node.get_interface_by_nailgun_network_name(
            admin_net)
        admin_ip_net = master_iface.l2_network_device.address_pool.ip_network

        params = {
            'ks': 'hd:LABEL=Mirantis_Fuel:/ks.cfg' if iso_connect_as == 'usb'
            else 'cdrom:/ks.cfg',
            'repo': 'hd:LABEL=Mirantis_Fuel:/',  # only required for USB boot
            'ip': master_iface.address_set.first().ip_address,
            'mask': admin_ip_net.netmask,
            'gw': admin_ip_net[1],
            'hostname': hostname,
            'nat_interface': nat_interface,
            'dns1': dns,
            'showmenu': 'no',
            'wait_for_external_config': 'yes',
            'build_images': '1' if build_images else '0',
            'iface': iface,
        }
        ready_keys = keys.format(**params)

        self.node.destroy()
        self._wipe_disks()
        self.node.start()
        wait(self.node.is_active, 60)
        self.node.send_keys(ready_keys)

    def wait_for_ssh(self, admin_net=settings.SSH_CREDENTIALS['admin_network'],
                     port=22, timeout=1200):
        ip = self.node.get_ip_address_by_nailgun_network_name(admin_net)
        is_port_active = partial(tcp_ping, ip)
        wait(is_port_active, timeout=timeout, timeout_msg="Waining SSH port")

    def _get_ssh_with_password(self, admin_net, login, password):
        ip = self.node.get_ip_address_by_nailgun_network_name(admin_net)
        try:
            ssh_client = SSHClient(ip, username=login, password=password)
            logger.debug('Accessing master node using SSH: SUCCESS')
        except Exception:
            logger.debug('Accessing master node using SSH credentials:'
                         ' FAIL, trying to change password from default')

            ssh_client = SSHClient(ip, username='root', password='r00tme')
            cmd = 'echo -e "{1}\\n{1}" | passwd {0}'.format(login, password)
            ssh_client.check_call(cmd)
            logger.debug("Master node password has changed.")

        return ssh_client

    def get_config(self,
                   admin_net=settings.SSH_CREDENTIALS['admin_network'],
                   login=settings.SSH_CREDENTIALS['login'],
                   password=settings.SSH_CREDENTIALS['password'],
                   fname='/etc/fuel/astute.yaml'):

        ssh_client = self._get_ssh_with_password(admin_net=admin_net,
                                                 login=login,
                                                 password=password)
        with ssh_client.open(fname, 'r') as f:
            return yaml.load(f)

    def save_config(self, conf,
                    admin_net=settings.SSH_CREDENTIALS['admin_network'],
                    login=settings.SSH_CREDENTIALS['login'],
                    password=settings.SSH_CREDENTIALS['password'],
                    fname='/etc/fuel/astute.yaml'):
        ssh_client = self._get_ssh_with_password(admin_net=admin_net,
                                                 login=login,
                                                 password=password)
        yaml_content = yaml.dump(conf, default_style='"',
                                 default_flow_style=False)
        with ssh_client.open(fname, 'w') as f:
            f.write(yaml_content)

    def config_update_router(self, conf, admin_net='admin'):
        master_iface = self.node.get_interface_by_nailgun_network_name(
            admin_net)
        admin_ip_net = master_iface.l2_network_device.address_pool.ip_network
        router = admin_ip_net[1]

        conf['DNS_UPSTREAM'] = router
        conf['ADMIN_NETWORK']['dhcp_gateway'] = router

    def wait_deploy_end(self, puppet_timeout=6000,
                        admin_net=settings.SSH_CREDENTIALS['admin_network'],
                        login=settings.SSH_CREDENTIALS['login'],
                        password=settings.SSH_CREDENTIALS['password'],
                        log_path="/var/log/puppet/bootstrap_admin_node.log",
                        phrase='Fuel node deployment complete'):
        logger.info("Waiting while bootstrapping is in progress")
        logger.info("Puppet timeout set in {0}".format(float(puppet_timeout)))

        ssh_client = self._get_ssh_with_password(admin_net=admin_net,
                                                 login=login,
                                                 password=password)
        with ssh_client:
            self._kill_wait_for_external_config(ssh_client)

            cmd = "grep '{0}' '{1}'".format(phrase, log_path)
            wait(lambda: not ssh_client.execute(cmd)['exit_code'],
                 timeout=(float(puppet_timeout)))

    def _kill_wait_for_external_config(self, ssh_client):
        kill_cmd = 'pkill -f "^wait_for_external_config"'
        ssh_client.check_call(kill_cmd)

        check_cmd = 'pkill -0 -f "^wait_for_external_config"; [[ $? -eq 1 ]]'
        ssh_client.check_call(check_cmd)

    def _wipe_disks(self):
        """Purge system disk on node

        param: node: Node
        param: disk_size: Integer
            :rtype : None
        """
        empty_file_name = '/tmp/empty8mb.data'
        create_empty_file(empty_file_name, size=8)

        disks = self.node.disk_devices
        for disk in disks:
            if (disk.device == 'disk' and
                    disk.volume.name == 'system' and
                    disk.volume.get_allocation() > 1024 ** 2):
                disk.volume.upload(empty_file_name)
