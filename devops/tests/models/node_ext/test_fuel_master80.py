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

import mock

from devops.models.node_ext.fuel_master80 import NodeExtension
from devops.tests.driver.driverless import DriverlessTestCase


class TestFuelMaster80Ext(DriverlessTestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        super(TestFuelMaster80Ext, self).setUp()

        self.node = self.group.add_node(
            name='test-node',
            role='fuel_master80')
        self.node.add_volume(
            name='system')
        self.node.add_volume(
            name='iso')

        self.adm_iface = self.node.add_interface(
            label='eth0',
            l2_network_device_name='admin',
            interface_model='e1000')

        self.node.add_network_config(
            label='eth0',
            networks=['fuelweb_admin'])

        self.node.kernel_cmd = (
            "<Wait>\n"
            "<Wait>\n"
            "<Wait>\n"
            "<Esc>\n"
            "<Wait>\n"
            "vmlinuz initrd=initrd.img ks=cdrom:/ks.cfg\n"
            " ip={ip}::{gw}:{mask}:{hostname}"
            ":enp0s3:off::: dns1={dns1}"
            " showmenu=no\n"
            " wait_for_external_config=no\n"
            " build_images=0\n"
            " <Enter>\n")

        self.send_keys_mock = self.patch('devops.models.Node.send_keys',
                                         create=True)
        self.wait_tcp_mock = self.patch('devops.models.node.wait_tcp')
        self.wait_ssh_cmd_mock = self.patch('devops.models.node.wait_ssh_cmd')

        self.node_ext = NodeExtension(self.node)

    def test_send_keys(self):
        self.node_ext._send_keys(self.node.kernel_cmd)
        self.send_keys_mock.assert_called_once_with(
            '<Wait>\n'
            '<Wait>\n'
            '<Wait>\n'
            '<Esc>\n'
            '<Wait>\n'
            'vmlinuz initrd=initrd.img ks=cdrom:/ks.cfg\n'
            ' ip=10.109.0.2::10.109.0.1:255.255.255.0:nailgun.domain.local'
            ':enp0s3:off::: dns1=8.8.8.8'
            ' showmenu=no\n'
            ' wait_for_external_config=no\n'
            ' build_images=0\n'
            ' <Enter>\n')

    def test_get_kernel_cmd_cdrom(self):
        assert self.node_ext.get_kernel_cmd(
            boot_from='cdrom', iface='enp0s3',
            wait_for_external_config='yes') == (
            '<Wait>\n'
            '<Wait>\n'
            '<Wait>\n'
            '<Esc>\n'
            '<Wait>\n'
            'vmlinuz initrd=initrd.img ks=cdrom:/ks.cfg\n'
            ' ip={ip}::{gw}:{mask}:{hostname}'
            ':enp0s3:off::: dns1={dns1}'
            ' showmenu=no\n'
            ' wait_for_external_config=yes\n'
            ' build_images=0\n'
            ' <Enter>\n')

    def test_get_kernel_cmd_usb(self):
        assert self.node_ext.get_kernel_cmd(
            boot_from='usb', iface='eth0',
            wait_for_external_config='no') == (
            '<Wait>\n'
            '<Wait>\n'
            '<Wait>\n'
            '<F12>\n'
            '2\n'
            '<Esc><Enter>\n'
            '<Wait>\n'
            'vmlinuz initrd=initrd.img ks=hd:LABEL=Mirantis_Fuel:/ks.cfg\n'
            ' repo=hd:LABEL=Mirantis_Fuel:/\n'
            ' ip={ip}::{gw}:{mask}:{hostname}'
            ':eth0:off::: dns1={dns1}'
            ' showmenu=no\n'
            ' wait_for_external_config=no\n'
            ' build_images=0\n'
            ' <Enter>\n')

    def test_get_deploy_check_cmd(self):
        assert self.node_ext.get_deploy_check_cmd() == (
            "grep 'Fuel node deployment complete' "
            "'/var/log/puppet/bootstrap_admin_node.log'")

    def test_bootstrap(self):
        self.node.bootstrap_and_wait()
        self.send_keys_mock.assert_called_once_with(
            '<Wait>\n'
            '<Wait>\n'
            '<Wait>\n'
            '<Esc>\n'
            '<Wait>\n'
            'vmlinuz initrd=initrd.img ks=cdrom:/ks.cfg\n'
            ' ip=10.109.0.2::10.109.0.1:255.255.255.0:nailgun.domain.local'
            ':enp0s3:off::: dns1=8.8.8.8'
            ' showmenu=no\n'
            ' wait_for_external_config=no\n'
            ' build_images=0\n'
            ' <Enter>\n')
        self.wait_tcp_mock.assert_called_once_with(
            host='10.109.0.2', port=22, timeout=600)

    def test_bootstrap_default(self):
        self.node.kernel_cmd = None
        self.node.bootstrap_and_wait()
        self.send_keys_mock.assert_called_once_with(
            '<Wait>\n'
            '<Wait>\n'
            '<Wait>\n'
            '<Esc>\n'
            '<Wait>\n'
            'vmlinuz initrd=initrd.img ks=cdrom:/ks.cfg\n'
            ' ip=10.109.0.2::10.109.0.1:255.255.255.0:nailgun.domain.local'
            ':enp0s3:off::: dns1=8.8.8.8'
            ' showmenu=no\n'
            ' wait_for_external_config=yes\n'
            ' build_images=0\n'
            ' <Enter>\n')
        self.wait_tcp_mock.assert_called_once_with(
            host='10.109.0.2', port=22, timeout=600)

    def test_deploy_wait(self):
        self.node.deploy_wait()
        check_cmd = ("grep 'Fuel node deployment complete' "
                     "'/var/log/puppet/bootstrap_admin_node.log'")
        self.wait_ssh_cmd_mock.assert_called_once_with(
            check_cmd=check_cmd,
            host='10.109.0.2', password='r00tme',
            port=22, timeout=3600, username='root')
