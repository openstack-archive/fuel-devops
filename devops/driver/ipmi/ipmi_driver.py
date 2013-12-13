#    Copyright 2013 Mirantis, Inc.
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


import logging
import os
import shutil
import subprocess
import time

from contextlib import contextmanager
from devops.helpers.retry import retry
from devops import error

LOGGER = logging.getLogger(__name__)


class DevopsDriver(object):
    def __getattr__(self, name):
        """
        Default method for all unimplemented functions
        """
        def default_method(*args, **kwargs):
            LOGGER.debug('Call of unimplemented method detected. '
                         'Method is {0}{1}{2}'.format(name, args, kwargs))
        return default_method

    def __init__(self,
                 ipmi_user, ipmi_password, ipmi_host,
                 ipmi_driver_root_dir='/tmp/devops_net_install',
                 ip_install_server='10.20.0.1',
                 ip_admin_node='10.20.0.2',
                 fuel_iso_path='/tmp/fuel.iso',
                 interface_install_server='eth0',
                 syslinux_dir='/usr/share/syslinux/',
                 system_init='not_systemd',
                 **driver_parameters):
        self.ipmi_cmd = ['/usr/bin/ipmitool', '-l', 'lan',
                         '-H', ipmi_host, '-U', ipmi_user, '-P', ipmi_password]
        self.ipmi_driver_root_dir = ipmi_driver_root_dir
        self.syslinux_dir = syslinux_dir
        self.ip_install_server = ip_install_server
        self.ip_node_admin = ip_admin_node
        self.fuel_iso_path = fuel_iso_path
        self.interface_install_server = interface_install_server
        self.system_init = system_init
        self._check_system_ready()

    def _check_system_ready(self):
        must_have_commands = [
            '/usr/bin/ipmitool',
            '/usr/sbin/dnsmasq',
            '/usr/sbin/rpc.nfsd']
        for command in must_have_commands:
            if not os.path.isfile(command):
                raise error.DevopsEnvironmentError(command)
        return True

    def node_reset(self):
        LOGGER.debug('Resetting server via IPMI')
        cmd = self.ipmi_cmd + ['power', 'reset']
        output = subprocess.check_output(cmd)
        LOGGER.debug('Reset output: %s' % output)
        return True

    def node_reboot(self):
        LOGGER.debug('Reboot server via IPMI')
        cmd = self.ipmi_cmd + ['power', 'cycle']
        output = subprocess.check_output(cmd)
        LOGGER.debug('Reboot server output: {0}'.format(output))
        return True

    def node_shutdown(self):
        LOGGER.debug('Off server via IPMI')
        cmd = self.ipmi_cmd + ['power', 'off']
        output = subprocess.check_output(cmd)
        LOGGER.debug('Off server output: {0}'.format(output))
        return True

    @retry(20, 30)
    def set_node_boot(self, device):
        """
        Valid are:
        pxe,
        disk,
        """
        LOGGER.debug('Set boot device to %s' % device)
        cmd = self.ipmi_cmd + ['chassis', 'bootdev', device]
        output = subprocess.check_output(cmd)
        LOGGER.debug('Set boot server output: {0}'.format(output))
        return True

    def get_node_power(self):
        LOGGER.debug('Get server power')
        cmd = self.ipmi_cmd + ['power', 'status']
        output = subprocess.check_output(cmd)
        LOGGER.debug('Set boot server output: {0}'.format(output))
        return True

    def admin_node_create(self):
        self._prepare_files()
        self._create_boot_menu()
        self._add_self_temp_ip()
        self._start_dhcp_tftp()
        self._start_nfs()
        self.set_node_boot('pxe')
        self.node_reset()
        time.sleep(60)
        self.set_node_boot('disk')
        self._stop_dhcp_tftp()

    def _clean_driver_file(self):
        self._stop_dhcp_tftp()
        self._stop_nfs()
        if subprocess.check_output('mount').find(
            '{0}/tftpboot/fuel'.format(
                self.ipmi_driver_root_dir)) > -1:
            cmd = ['sudo', 'umount',
                   '{0}/tftpboot/fuel'.format(self.ipmi_driver_root_dir)]
            subprocess.check_output(cmd)
        if os.path.isdir(self.ipmi_driver_root_dir):
            shutil.rmtree(self.ipmi_driver_root_dir)

    def _prepare_files(self):
        self._clean_driver_file()
        os.mkdir(self.ipmi_driver_root_dir)
        os.mkdir('{0}/tftpboot'.format(self.ipmi_driver_root_dir))
        os.mkdir('{0}/tftpboot/pxelinux.cfg'.format(self.ipmi_driver_root_dir))
        os.mkdir('{0}/tftpboot/fuel'.format(self.ipmi_driver_root_dir))
        syslinux_files = ['memdisk', 'menu.c32', 'poweroff.c32',
                          'pxelinux.0', 'reboot.c32', 'ldlinux.c32',
                          'libutil.c32']
        for i in syslinux_files:
            shutil.copy('{0}/{1}'.format(self.syslinux_dir, i),
                        '{0}/tftpboot/'.format(self.ipmi_driver_root_dir))
        cmd = ['sudo', 'mount', '-o', 'loop', self.fuel_iso_path,
               '{0}/tftpboot/fuel'.format(self.ipmi_driver_root_dir)]
        subprocess.call(cmd)
        return True

    @contextmanager
    def _create_boot_menu(self, interface='eth0',
                          ks_script='tftpboot/fuel/ks.cfg'):
        LOGGER.debug('Create PXE boot menu for booting from network')
        menu_boot = ("DEFAULT menu.c32\n"
                     "prompt 0\n"
                     "MENU TITLE Fuel Installer\n"
                     "TIMEOUT 20\n"
                     "LABEL LABEL fuel\n"
                     "MENU LABEL Install ^FUEL\n"
                     "MENU DEFAULT\n"
                     "KERNEL /fuel/isolinux/vmlinuz\n"
                     "INITRD /fuel/isolinux/initrd.img\n"
                     "APPEND ks=nfs:{0}:{1}/{4} "
                     "ks.device='{3}' "
                     "repo=nfs:{0}:{1}/tftpboot/fuel/ ip={2} "
                     "netmask=255.255.255.0 dns1={0} "
                     "hostname=fuel.mirantis.com ".
                     format(self.ip_install_server,
                            self.ipmi_driver_root_dir,
                            self.ip_node_admin,
                            interface,
                            ks_script))
        with open('{0}/tftpboot/pxelinux.cfg/default'.
                  format(self.ipmi_driver_root_dir, 'w')) as f:
            f.write(menu_boot)

        return True

    def _add_self_temp_ip(self):
        #Check all IPs
        cmd = ['sudo', 'ip', 'addr', 'sh']
        output = subprocess.check_output(cmd)
        if output.find(self.ip_install_server) > -1:
            cmd = ['sudo', 'ip', 'addr', 'show', 'dev',
                   self.interface_install_server]
            output = subprocess.check_output(cmd)
            if output.find(self.ip_install_server) > -1:
                LOGGER.debug('ip {0} already set on the interface {1}'.
                             format((self.ip_install_server,
                                     self.interface_install_server)))
                return
            else:
                LOGGER.debug('ip {0} already set on the another interface'.
                             format(self.ip_install_server))

        cmd = ['sudo', 'ip', 'addr', 'add', '{0}/24'.
               format(self.ip_install_server),
               'dev', self.interface_install_server]
        output = subprocess.check_output(cmd)
        LOGGER.debug('Added ip address {0} to {0} . Output is :{1}'.
                     format(self.ip_install_server,
                            self.interface_install_server,
                            output))
        return True

    def _start_dhcp_tftp(self):
        cmd = ['sudo', 'dnsmasq',
               '--enable-tftp',
               '--tftp-root={0}/tftpboot'.format(self.ipmi_driver_root_dir),
               '--dhcp-range={0},{0}'.format(self.ip_node_admin),
               '--port=0', '--interface={0}'.
               format(self.interface_install_server),
               "--dhcp-boot=pxelinux.0",
               '--pid-file={0}/dnsmasq.pid'.format(self.ipmi_driver_root_dir)]

        subprocess.call(cmd)
        return True

    def _stop_dhcp_tftp(self):
        if os.path.isfile('{0}/dnsmasq.pid'.format(self.ipmi_driver_root_dir)):
            try:
                pid_file = open('{0}/dnsmasq.pid'.
                                format(self.ipmi_driver_root_dir), 'r')
                for line in pid_file:
                    pid = line.strip().lower()
                    cmd = ['sudo', 'kill', pid]
                    subprocess.call(cmd)
                pid_file.close()
                LOGGER.debug('dnsmasq killed')
            except subprocess.CalledProcessError, e:
                LOGGER.warning("Can't stop dnsmasq: {0}".format(e.output))
        return True

    def _start_nfs(self):
        if os.path.isfile('/etc/exports'):
            cmd = ['sudo', 'mv', '/etc/exports', '/etc/exports-devops-last']
            output = subprocess.check_output(cmd)
            print(output)
        cmd = ['sudo', 'touch', '/etc/exports']
        subprocess.call(cmd)
        cmd = ['sudo', 'chown', os.getlogin(), '/etc/exports']
        subprocess.call(cmd)
        f = open('/etc/exports', 'w+')
        f.write('{0}/tftpboot/fuel/ {1}(ro,async,no_subtree_check,fsid=1,'
                'no_root_squash)'.format(self.ipmi_driver_root_dir,
                                         self.ip_node_admin))
        f.close()
        if self.system_init.find('systemd') == 1:
            cmd = ['sudo', 'systemctl', 'restart', 'nfsd']
        else:
            cmd = ['sudo', 'service', 'nfs-kernel-server', 'restart']
        output = subprocess.check_output(cmd)
        LOGGER.debug('NFS server started, output is {0}'.format(output))
        return True

    def _stop_nfs(self):
        if os.path.isfile('/etc/exports-devops-last'):
            cmd = ['sudo', 'mv', '/etc/exports-devops-last', '/etc/exports']
            subprocess.call(cmd)
        if self.system_init.find('systemd') == 1:
            cmd = ['sudo', 'systemctl', 'stop', 'nfsd']
        else:
            cmd = ['sudo', 'service', 'nfs-kernel-server', 'stop']
        output = subprocess.check_output(cmd)
        LOGGER.debug('NFS server stopped, output is {0}'.format(output))
        return True
