# vim: ts=4 sw=4 expandta
# -*- coding: ascii -*-

import logging
import os
import subprocess
import shutil
import time

from devops.helpers.retry import retry

logger = logging.getLogger(__name__)


class DevopsDriver(object):
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
        self.ipmi_cmd = ['/usr/sbin/ipmitool', '-l', 'lan',
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
        if not os.path.isfile('/usr/sbin/ipmitool'):
            raise Exception('/usr/sbin/ipmitool is not found')
        if not os.path.isdir(self.syslinux_dir):
            raise Exception('{} is not found'.format(self.syslinux_dir))
        if not os.path.isfile('/usr/sbin/dnsmasq'):
            raise Exception('/usr/sbin/dnsmasq is not found')
        if not os.path.isfile('/usr/sbin/rpc.nfsd'):
            raise Exception('NFSd (/usr/sbin/rpc.nfsd) is not found')
        return True

    def node_reset(self):
        logger.debug('Resetting server via IPMI')
        cmd = self.ipmi_cmd + ['power', 'reset']
        output = subprocess.check_output(cmd)
        logger.debug('Reset output: %s' % output)
        return True

    def node_reboot(self):
        logger.debug('Reboot server via IPMI')
        cmd = self.ipmi_cmd + ['power', 'cycle']
        output = subprocess.check_output(cmd)
        logger.debug('Reboot server output: {}'.format(output))
        return True

    def node_shutdown(self):
        logger.debug('Off server via IPMI')
        cmd = self.ipmi_cmd + ['power', 'off']
        output = subprocess.check_output(cmd)
        logger.debug('Off server output: {}'.format(output))
        return True

    @retry(20, 30)
    def set_node_boot(self, device):
        """
        Valid are:
        pxe,
        disk,
        """
        logger.debug('Set boot device to %s' % device)
        cmd = self.ipmi_cmd + ['chassis', 'bootdev', device]
        output = subprocess.check_output(cmd)
        logger.debug('Set boot server output: {}'.format(output))
        return True

    def get_node_power(self):
        logger.debug('Get server power')
        cmd = self.ipmi_cmd + ['power', 'status']
        output = subprocess.check_output(cmd)
        logger.debug('Set boot server output: {}'.format(output))
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
            '{}/tftpboot/fuel'.format(
                self.ipmi_driver_root_dir)) > -1:
            cmd = ['sudo', 'umount',
                   '{}/tftpboot/fuel'.format(self.ipmi_driver_root_dir)]
            subprocess.check_output(cmd)
        if os.path.isdir(self.ipmi_driver_root_dir):
            shutil.rmtree(self.ipmi_driver_root_dir)

    def _prepare_files(self):
        self._clean_driver_file()
        os.mkdir(self.ipmi_driver_root_dir)
        os.mkdir('{}/tftpboot'.format(self.ipmi_driver_root_dir))
        os.mkdir('{}/tftpboot/pxelinux.cfg'.format(self.ipmi_driver_root_dir))
        os.mkdir('{}/tftpboot/fuel'.format(self.ipmi_driver_root_dir))
        syslinux_files = ['memdisk', 'menu.c32', 'poweroff.c32',
                          'pxelinux.0', 'reboot.c32', 'ldlinux.c32',
                          'libutil.c32']
        for i in syslinux_files:
            shutil.copy('{0}/{1}'.format(self.syslinux_dir, i),
                        '{}/tftpboot/'.format(self.ipmi_driver_root_dir))
        cmd = ['sudo', 'mount', '-o', 'loop', self.fuel_iso_path,
               '{}/tftpboot/fuel'.format(self.ipmi_driver_root_dir)]
        subprocess.call(cmd)
        return True

    def _create_boot_menu(self, interface='eth0',
                          ks_script='tftpboot/fuel/ks.cfg'):
        logger.debug('Create PXE boot menu for booting from network')
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
                     "hostname=fuel.mirantis.com ".format(
                     self.ip_install_server, self.ipmi_driver_root_dir,
                     self.ip_node_admin, interface, ks_script))
        f = open('%s/tftpboot/pxelinux.cfg/default' % self.ipmi_driver_root_dir, 'w')
        f.write(menu_boot)
        f.close()
        return True

    def _add_self_temp_ip(self):
        #Check all IPs
        cmd = ['sudo', 'ip', 'addr', 'sh']
        output = subprocess.check_output(cmd)
        if output.find(self.ip_install_server) > -1:
            cmd = ['sudo', 'ip', 'addr', 'show', 'dev', self.interface_install_server]
            output = subprocess.check_output(cmd)
            if output.find(self.ip_install_server) > -1:
                logger.debug('ip %s already set on the interface %s' %
                             (self.ip_install_server,
                              self.interface_install_server))
                return
            else:
                logger.debug('ip %s already set on the another interface' %
                             self.ip_install_server)

        cmd = ['sudo', 'ip', 'addr', 'add', '%s/24' % self.ip_install_server,
               'dev', self.interface_install_server]
        output = subprocess.check_output(cmd)
        logger.debug('Added ip address %s to %s . Output is :%s' % (
            self.ip_install_server, self.interface_install_server, output))
        return True

    def _start_dhcp_tftp(self):
        cmd = ['sudo', 'dnsmasq',
               '--enable-tftp',
               '--tftp-root=%s/tftpboot' % self.ipmi_driver_root_dir,
               '--dhcp-range={0:s},{1:s}'.format(self.ip_node_admin, self.ip_node_admin),
               '--port=0', '--interface=%s' % self.interface_install_server,
               "--dhcp-boot=pxelinux.0",
               '--pid-file=%s/dnsmasq.pid' % self.ipmi_driver_root_dir]

        subprocess.call(cmd)
        return True

    def _stop_dhcp_tftp(self):
        if os.path.isfile('{}/dnsmasq.pid'.format(self.ipmi_driver_root_dir)):
            try:
                pid_file = open('{}/dnsmasq.pid'.format(self.ipmi_driver_root_dir), 'r')
                for line in pid_file:
                    pid = line.strip().lower()
                    cmd = ['sudo', 'kill', pid]
                    subprocess.call(cmd)
                pid_file.close()
                logger.debug('dnsmasq killed')
            except subprocess.CalledProcessError, e:
                logger.warning("Can't stop dnsmasq: {}".format(e.output))
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
        logger.debug('NFS server started, output is {}'.format(output))
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
        logger.debug('NFS server stopped, output is {}'.format(output))
        return True







