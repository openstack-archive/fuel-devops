# -*- coding: utf-8 -*-

#    Copyright 2015 - 2016 Mirantis, Inc.
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
import unittest

import mock

from devops.helpers.cloud_image_settings import generate_cloud_image_settings


class TestCloudImageSettings(unittest.TestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        self.subprocess_mock = self.patch(
            'devops.helpers.cloud_image_settings.subprocess', autospec=True)

        self.os_mock = self.patch(
            'devops.helpers.cloud_image_settings.os', autospec=True)
        self.os_mock.path.exists.return_value = False
        self.os_mock.path.join = os.path.join
        self.os_mock.path.dirname = os.path.dirname

        self.open_mock = mock.mock_open()
        self.patch('devops.helpers.cloud_image_settings.open', self.open_mock,
                   create=True)

    def test_generate_cloud_image_settings(self):
        generate_cloud_image_settings(
            admin_ip='10.109.0.2',
            admin_netmask='255.255.255.0',
            admin_network='10.109.0.0/24',
            cloud_image_settings_path='/mydir/cloud_settings.iso',
            meta_data_path='/mydir/meta-data',
            user_data_path='/mydir/user-data',
            gateway='10.109.0.1',
            hostname='nailgun.domain.local',
            interface_name=u'enp0s3')

        self.os_mock.makedirs.assert_called_once_with('/mydir')

        self.open_mock.assert_has_calls((
            mock.call('/mydir/meta-data', 'w'),
            mock.call().__enter__(),
            mock.call().write(
                'instance-id: iid-local1\n'
                'network-interfaces: |\n'
                ' auto enp0s3\n'
                ' iface enp0s3 inet static\n'
                ' address 10.109.0.2\n'
                ' network 10.109.0.0/24\n'
                ' netmask 255.255.255.0\n'
                ' gateway 10.109.0.1\n'
                ' dns-nameservers 8.8.8.8\n'
                'local-hostname: nailgun.domain.local'),
            mock.call().__exit__(None, None, None),
            mock.call('/mydir/user-data', 'w'),
            mock.call().__enter__(),
            mock.call().write(
                "\n"
                "#cloud-config\n"
                "ssh_pwauth: True\n"
                "chpasswd:\n"
                " list: |\n"
                "  root:r00tme\n"
                " expire: False\n"
                "\n"
                "runcmd:\n"
                " - sudo ifup enp0s3\n"
                " - sudo sed -i -e '/^PermitRootLogin/s/^.*$/PermitRootLogin "
                "yes/' /etc/ssh/sshd_config\n"
                " - sudo service ssh restart\n"
                " - sudo route add default gw 10.109.0.1 enp0s3"),
            mock.call().__exit__(None, None, None),
        ))

        self.subprocess_mock.check_call.assert_called_once_with(
            'genisoimage -output /mydir/cloud_settings.iso '
            '-volid cidata -joliet -rock /mydir/user-data '
            '/mydir/meta-data', shell=True)
