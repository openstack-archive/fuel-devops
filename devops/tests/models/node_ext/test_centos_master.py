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

import collections

import mock

from devops import models
from devops.tests.driver.libvirt.base import LibvirtTestCase
from django.conf import settings


class TestCentosMasterExt(LibvirtTestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        super(TestCentosMasterExt, self).setUp()

        self.open_mock = mock.mock_open(read_data='image_data')
        self.patch('devops.driver.libvirt.libvirt_driver.open',
                   self.open_mock, create=True)

        self.os_mock = self.patch('devops.helpers.helpers.os')
        Size = collections.namedtuple('Size', ['st_size'])
        self.file_sizes = {
            '/tmp/test/cloud_settings.iso': Size(st_size=1 * 1024 ** 3),
        }
        self.os_mock.stat.side_effect = self.file_sizes.get

        # Environment with an 'admin' network

        self.env = models.Environment.create('test')
        self.group = self.env.add_group(
            group_name='test_group',
            driver_name='devops.driver.libvirt',
            connection_string='test:///default',
            storage_pool_name='default-pool')

        self.pub_ap = self.env.add_address_pool(
            name='admin-pool01', net='10.109.0.0/16:24', tag=0,
            ip_reserved=dict(gateway=1, l2_network_device=1),
            ip_ranges=dict(default=[2, -2]))
        self.group.add_l2_network_device(
            name='admin', address_pool='admin-pool01')

        self.node = self.group.add_node(
            name='test-node',
            role='centos_master',
            architecture='x86_64',
            hypervisor='test')

        self.system_volume = self.node.add_volume(name='system', capacity=10)
        self.iso_volume = self.node.add_volume(name='iso', capacity=5)

        self.adm_iface = self.node.add_interface(
            label='enp0s3',
            l2_network_device_name='admin',
            mac_address='64:c6:27:47:14:83',
            interface_model='e1000')

        self.node.add_network_config(
            label='enp0s3',
            networks=['fuelweb_admin'])

        self.wait_tcp_mock = self.patch(
            'devops.helpers.helpers.wait_tcp')

    @mock.patch(
        'devops.helpers.subprocess_runner.Subprocess', autospec=True)
    @mock.patch('devops.driver.libvirt.libvirt_driver.uuid')
    @mock.patch('libvirt.virConnect.defineXML')
    @mock.patch.multiple(settings, CLOUD_IMAGE_DIR='/tmp/')
    def test_001_pre_define(self, define_xml_mock, uuid_mock, subprocess):
        uuid_mock.uuid4.side_effect = (
            mock.Mock(hex='fe527bd28e0f4a84b9117dc97142c580'),
            mock.Mock(hex='9cddb80fe82e480eb14c1a89f1c0e11d'),
            mock.Mock(hex='885674d28e0f4a84b265625673674565'),
            mock.Mock(hex='91252350fe82e480eb14c1a89f1c0234'))
        define_xml_mock.return_value.UUIDString.return_value = 'fake_uuid'

        self.system_volume.define()
        self.iso_volume.define()
        self.node.define()

        assert self.node.cloud_init_iface_up == 'enp0s3'

        assert self.node.cloud_init_volume_name == 'iso'

        volume = self.node.get_volume(
            name=self.node.cloud_init_volume_name)

        assert volume.cloudinit_meta_data == (
            "instance-id: iid-local1\n"
            "network-interfaces: |\n"
            " auto {interface_name}\n"
            " iface {interface_name} inet static\n"
            " address {address}\n"
            " network {network}\n"
            " netmask {netmask}\n"
            " gateway {gateway}\n"
            " dns-nameservers 8.8.8.8\n"
            "local-hostname: nailgun.domain.local")

        assert volume.cloudinit_user_data == (
            "\n#cloud-config\n"
            "ssh_pwauth: True\n"
            "chpasswd:\n"
            " list: |\n"
            "  root:r00tme\n"
            " expire: False\n\n"
            "runcmd:\n"
            " - sudo ifup {interface_name}\n"
            " - sudo sed -i -e '/^PermitRootLogin/s/^.*$/PermitRootLogin yes/'"
            " /etc/ssh/sshd_config\n"
            " - sudo service ssh restart\n"
            " - sudo route add default gw {gateway} {interface_name}")

    def test_002_deploy_wait(self):
        self.node.ext.deploy_wait()

    def test_003_get_kernel_cmd(self):
        assert self.node.ext.get_kernel_cmd() is None

    @mock.patch('devops.driver.libvirt.Node.is_active')
    def test_004_bootstrap_and_wait(self, is_active_mock):
        is_active_mock.return_value = True
        self.node.ext.bootstrap_and_wait()
        self.wait_tcp_mock.assert_called_once_with(
            host='10.109.0.2', port=22, timeout=600,
            timeout_msg=mock.ANY)
