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

import subprocess
import os.path
import shutil

import SimpleHTTPServer
import SocketServer

# PORT = 8000

# Handler = SimpleHTTPServer.SimpleHTTPRequestHandler

# httpd = SocketServer.TCPServer(("", PORT), Handler)

# print "serving at port", PORT


def admin_wait_bootstrap(puppet_timeout, env):
    """Login to master node and waiting end of installation

    param: puppet_timeout: Integer
    param: env: Environment
        :rtype : None
    """

    print("Waiting while bootstrapping is in progress")
    print("Puppet timeout set in {0}").format(puppet_timeout)
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
                        dns1=MASTER_DNS
                        ):
    """Change master node configuration via kernel param

    param: admin_node: Node
    param: hostname: String
    param: dns1: String
        :rtype : None
    """
    admin_net = admin_node.environment.get_network(name='admin')
    keys = get_keys(
        ip=admin_node.get_ip_address_by_network_name('admin'),
        mask=admin_net.netmask,
        gw=admin_net.default_gw,
        hostname=hostname,
        nat_interface='',
        dns1=dns1,
        showmenu='no',
        build_images=0)

    print("Waiting for admin node to start up")
    wait(lambda: admin_node.driver.node_active(admin_node), 60)
    print("Proceed with installation")
    admin_node.send_keys(keys)


def admin_node_create(self):
    prepare_files()
    create_boot_menu()
    # self._add_self_temp_ip()
    # self._start_dhcp_tftp()
    # self._start_nfs()
    self.set_node_boot('pxe')
    self.node_reset()
    time.sleep(60)
    self.set_node_boot('disk')
    # self._stop_dhcp_tftp()


def clean_tftp_dir(tftp_dir):
    if os.path.exists('{}/fuel'.format(tftp_dir)):
        cmd = ['fusermount', '-u', '{}/fuel'.format(tftp_dir)]
        subprocess.call(cmd)
        # cmd = ['rmdir', '{}/fuel'.format(tftp_dir)]
        # subprocess.check_output(cmd)
    if os.path.isdir(tftp_dir):
        shutil.rmtree(tftp_dir)


def prepare_files(tftp_dir, fuel_iso_path, syslinux_dir='/usr/lib/syslinux'):
    clean_tftp_dir(tftp_dir)
    os.mkdir(tftp_dir)
    # os.mkdir('{0}/tftpboot'.format(tftp_dir))
    os.mkdir('{0}/pxelinux.cfg'.format(tftp_dir))
    # os.mkdir('{0}/tftpboot/fuel'.format(tftp_dir))
    syslinux_files = ['memdisk', 'menu.c32', 'poweroff.com', #'poweroff.c32',
                      'pxelinux.0', 'reboot.c32'] # 'ldlinux.c32',
                      # 'libutil.c32']
    for i in syslinux_files:
        shutil.copy('{0}/{1}'.format(syslinux_dir, i),
                    '{0}/'.format(tftp_dir))
    # cmd = ['mkdir', '{}/fuel'.format(tftp_dir)]
    # subprocess.call(cmd)
    cmd = ['fuseiso', '-p', fuel_iso_path,
           '{0}/fuel'.format(tftp_dir)]
    subprocess.call(cmd)
    shutil.copytree('{0}/fuel/isolinux'.format(tftp_dir),
                    '{0}/isolinux'.format(tftp_dir), symlinks=False, ignore=None)
    start_web_server(tftp_dir, port=8000)
    return True


def create_boot_menu(admin_node, tftp_dir, interface='eth0',
                     hostname=MASTER_FQDN, dns1=MASTER_DNS,
                     showmenu='no', nat_interface=''):
    admin_net = admin_node.environment.get_network(name='admin')
    print('Create PXE boot menu for booting from network')
    menu_boot = ("DEFAULT menu.c32\n"
                 "prompt 0\n"
                 "MENU TITLE Fuel Installer\n"
                 "TIMEOUT 20\n"
                 "LABEL LABEL fuel\n"
                 "MENU LABEL Install ^FUEL\n"
                 "MENU DEFAULT\n"
                 "KERNEL /isolinux/vmlinuz\n"
                 "INITRD /isolinux/initrd.img\n"
                 "APPEND ks=http://{server_ip}:8000/fuel/ks.cfg "
                 "ksdevice={interface} "
                 "repo=http://{server_ip}:8000/fuel "
                 "ip={ip} "
                 "gw={gw} "
                 "netmask={mask} "
                 "dns1={dns1} "
                 "hostname={hostname} "
                 "nat_interface={nat_interface} "
                 "showmenu={showmenu}".
                 format(server_ip=admin_net.ip[1],
                        ip=admin_node.get_ip_address_by_network_name('admin'),
                        gw=admin_net.default_gw,
                        mask=admin_net.netmask,
                        interface=interface,
                        hostname=hostname,
                        nat_interface=nat_interface,
                        dns1=dns1,
                        showmenu=showmenu))
    with open('{0}/pxelinux.cfg/default'.format(tftp_dir), 'w') as f:
        f.write(menu_boot)

    return True


def start_web_server(docroot, port=8000):
    # Handler = SimpleHTTPServer.SimpleHTTPRequestHandler
    # httpd = SocketServer.TCPServer(("", port), Handler)
    # return httpd
    cmd = ['twistd', '--logfile=/tmp/twisted.log',
           '--pidfile=/tmp/twisted.pid', '-n', 'web',
           '-p', str(port), '--path', docroot]
    subprocess.Popen(cmd)
    # cmd = ['cat', '/tmp/twisted.{0}.pid'.format(docroot)]
    # return subprocess.check_call(cmd)
    return True
