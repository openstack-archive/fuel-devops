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

from devops.helpers.helpers import get_admin_remote
from devops.helpers.helpers import get_keys
from devops.helpers.helpers import wait
from devops.models.network import DiskDevice
from devops.models.volume import Volume
from devops.settings import MASTER_BOOTSTRAP_LOG
from devops.settings import MASTER_DNS
from devops.settings import MASTER_FQDN
from devops.settings import WAIT_FOR_PROVISIONING_TIMEOUT
from devops.settings import SSH_CREDENTIALS


def admin_wait_bootstrap(puppet_timeout, env):
    """Login to master node and waiting end of installation

    param: puppet_timeout: Integer
    param: env: Environment
        :rtype : None
    """

    print("Waiting while bootstrapping is in progress")
    print("Puppet timeout set in {0}".format(puppet_timeout))
    wait(
        lambda: not
        get_admin_remote(env).execute(
            "grep 'Fuel node deployment complete' '%s'" % MASTER_BOOTSTRAP_LOG
        )['exit_code'],
        timeout=(float(puppet_timeout))
    )


def admin_prepare_disks(node, disk_size):
    """Purge system disk on node

    param: node: Node
    param: disk_size: Integer
        :rtype : None
    """

    disks = node.disk_devices
    for disk in disks:
        if (disk.device == 'disk' and
                disk.volume.name == 'admin-system' and
                disk.volume.get_allocation() > 1024 ** 2):

            print("Erasing system disk")
            disk.volume.erase()
            new_volume = Volume.volume_create(
                name="admin-system",
                capacity=disk_size * 1024 ** 3,
                environment=node.environment,
                format='qcow2')

            new_volume.define()
            DiskDevice.node_attach_volume(
                node=node,
                volume=new_volume,
                target_dev=disk.target_dev)


def admin_change_config(admin_node,
                        hostname=MASTER_FQDN,
                        dns1=MASTER_DNS,
                        admin_centos_version=7,
                        static_interface='eth0'
                        ):
    """Change master node configuration via kernel param

    param: admin_node: Node
    param: hostname: String
    param: dns1: String
        :rtype : None
    """
    # TODO(akostrikov) missing:
    #  set_admin_ssh_password
    #  setup_customisation
    #  nessus_node = NessusActions(self.d_env)
    #  nessus_node.add_nessus_node()
    #  self.admin_actions.modify_configs(self.d_env.router())
    #  self.kill_wait_for_external_config()

    admin_net = admin_node.environment.get_network(name='admin')
    admin_ip = admin_node.get_ip_address_by_network_name('admin')
    mask = admin_net.netmask
    gw = admin_net.default_gw
    hostname = hostname
    nat_interface = ''
    dns1 = dns1
    showmenu = 'no'
    build_images = 0
    keys = get_keys(
        admin_ip, mask, gw, hostname, nat_interface, dns1,
        showmenu, build_images, centos_version=7,
        static_interface='enp0s3',
        wait_for_external_config='yes')

    print('Waiting for admin node to start up')
    wait(lambda: admin_node.driver.node_active(admin_node), 60)

    print('Proceed with installation')
    admin_node.send_keys(keys)

    # wait_for_provisioning() analog
    admin_node.await('admin',
                     timeout=WAIT_FOR_PROVISIONING_TIMEOUT)

    # wait_for_external_config() analog
    check_cmd = 'pkill -0 -f wait_for_external_config'
    remote = admin_node.remote('admin',
                               login=SSH_CREDENTIALS['login'],
                               password=SSH_CREDENTIALS['password'])
    wait(
        lambda: remote.execute(check_cmd)['exit_code'] == 0, timeout=120)
