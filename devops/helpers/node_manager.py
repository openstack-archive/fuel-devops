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

from devops.helpers.helpers import _get_keys
from devops.helpers.helpers import get_admin_remote
from devops.helpers.helpers import wait
from devops.models.network import DiskDevice
from devops.models.volume import Volume


def admin_wait_bootstrap(puppet_timeout, env):

    print("Waiting while bootstrapping is in progress")
    log_path = "/var/log/puppet/bootstrap_admin_node.log"
    print("Puppet timeout set in {0}").format(puppet_timeout)
    wait(
        lambda: not
        get_admin_remote(env).execute(
            "grep 'Fuel node deployment complete' '%s'" % log_path
        )['exit_code'],
        timeout=(float(puppet_timeout))
    )


def admin_prepare_disks(admin_node, disk_size):

    disks = admin_node.disk_devices
    disk_size = disk_size * 1024 ** 3
    for disk in disks:
        if (disk.device == 'disk' and
                disk.volume.name == 'admin-system' and
                disk.volume.get_allocation() > 1024 ** 2):

            print("Erase system disk")
            disk.volume.erase()
            new_volume = Volume.volume_create(
                name="admin-system",
                capacity=disk_size,
                environment=admin_node.environment,
                format='qcow2')

            new_volume.define()
            DiskDevice.node_attach_volume(
                node=admin_node,
                volume=new_volume,
                target_dev=disk.target_dev)


def admin_change_config(admin_node):

    admin_net = admin_node.environment.get_network(name='admin')
    keys = _get_keys(
        ip=admin_node.get_ip_address_by_network_name('admin'),
        mask=admin_net.netmask,
        gw=admin_net.router,
        hostname='nailgun.test.domain.local',
        nat_interface='',
        dns1='8.8.8.8',
        showmenu='no')

    print("Waiting for admin node to start up")
    wait(lambda: admin_node.driver.node_active(admin_node), 60)
    print("Proceed with installation")
    admin_node.send_keys(keys)
