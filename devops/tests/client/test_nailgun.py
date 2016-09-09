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

from django.test import TestCase
from keystoneauth1.identity import V2Password
from keystoneauth1.session import Session as KeystoneSession
import mock

from devops.client import nailgun
from devops import error


class TestNailgunClient(TestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        super(TestNailgunClient, self).setUp()

        self.v2pass_mock = self.patch(
            'devops.client.nailgun.V2Password', spec=V2Password)
        self.v2pass_inst = self.v2pass_mock.return_value
        self.ks_session_mock = self.patch(
            'devops.client.nailgun.KeystoneSession', spec=KeystoneSession)
        self.k2_session_inst = self.ks_session_mock.return_value
        self.nodes_mock = self.k2_session_inst.get.return_value

        self.nc = nailgun.NailgunClient('10.109.0.2')

    def test_get_nodes_json(self):
        data = self.nc.get_nodes_json()
        assert data is self.nodes_mock.json.return_value

        self.v2pass_mock.assert_called_once_with(
            auth_url='http://10.109.0.2:5000/v2.0',
            password='admin', tenant_name='admin', username='admin')
        self.ks_session_mock.assert_called_once_with(
            auth=self.v2pass_inst, verify=False)
        self.k2_session_inst.get.assert_called_once_with(
            '/nodes', endpoint_filter={'service_type': 'fuel'})

    def test_get_slave_ip_by_mac(self):
        self.nodes_mock.json.return_value = [
            {
                'ip': '10.109.0.100',
                'meta': {
                    'interfaces': [
                        {'mac': '64.52.DC.96.12.CC'}
                    ]
                }
            }
        ]

        ip = self.nc.get_slave_ip_by_mac('64:52:dc:96:12:cc')
        assert ip == '10.109.0.100'
        ip = self.nc.get_slave_ip_by_mac('64.52.dc.96.12.cc')
        assert ip == '10.109.0.100'
        ip = self.nc.get_slave_ip_by_mac('6452dc9612cc')
        assert ip == '10.109.0.100'

        with self.assertRaises(error.DevopsError):
            self.nc.get_slave_ip_by_mac('a1a1a1a1a1a1')
