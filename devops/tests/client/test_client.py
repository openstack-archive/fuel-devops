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

from devops.client import client
from devops.client import environment
from devops import error
from devops.tests.driver import driverless


class TestDevopsClient(driverless.DriverlessTestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        super(TestDevopsClient, self).setUp()

        self.conf = {
            'template': {
                'devops_settings': {
                    'env_name': 'test2',
                    'address_pools': {
                        'pool1': {
                            'net': '10.109.0.0/16:24',
                            'params': {
                                'tag': 0,
                                'ip_reserved': {
                                    'gateway': 1,
                                    'l2_network_device': 1,
                                },
                                'ip_ranges': {
                                    'default': [2, -2]
                                }
                            }
                        }
                    },
                    'groups': [
                        {
                            'name': 'rack-01',
                            'driver': {
                                'name': 'devops.driver.empty',
                            },
                            'network_pools': {
                                'fuelweb_admin': 'pool1'
                            },
                            'l2_network_devices': {
                                'admin': {
                                    'address_pool': 'pool1',
                                }
                            }
                        }
                    ]
                }
            }
        }

        self.cr_conf_mock = self.patch(
            'devops.helpers.templates.create_devops_config')
        self.cr_conf_mock.return_value = self.conf

        self.get_conf_mock = self.patch(
            'devops.helpers.templates.get_devops_config')
        self.get_conf_mock.return_value = self.conf

        self.c = client.DevopsClient()

    def test_get_env(self):
        test_env = self.c.get_env('test')
        assert test_env.name == 'test'
        assert isinstance(test_env, environment.DevopsEnvironment)

    def test_get_env_error(self):
        with self.assertRaises(error.DevopsError):
            self.c.get_env('unknown')

    def test_list_env_names(self):
        assert self.c.list_env_names() == ['test']
        test_env = self.c.get_env('test')
        test_env.erase()
        assert self.c.list_env_names() == []

    def test_create_env_default(self):
        env = self.c.create_env(env_name='test2')
        assert env.name == 'test2'
        self.cr_conf_mock.assert_called_once_with(
            admin_iso_path=None,
            admin_memory=3072,
            admin_sysvolume_capacity=75,
            admin_vcpu=2,
            boot_from='cdrom',
            driver_enable_acpi=False,
            driver_enable_nwfilers=False,
            env_name='test2',
            ironic_nodes_count=0,
            multipath_count=0,
            networks_bonding=False,
            networks_bondinginterfaces={
                'admin': ['eth0', 'eth1'],
                'public': ['eth2', 'eth3', 'eth4', 'eth5']},
            networks_dhcp={
                'admin': False,
                'management': False,
                'storage': False,
                'public': False,
                'private': False},
            networks_forwarding={
                'admin': 'nat',
                'management': None,
                'storage': None,
                'public': 'nat',
                'private': None},
            networks_interfaceorder=[
                'admin',
                'public',
                'management',
                'private',
                'storage'],
            networks_multiplenetworks=False,
            networks_nodegroups=(),
            networks_pools={
                'admin': ['10.109.0.0/16', '24'],
                'management': ['10.109.0.0/16', '24'],
                'storage': ['10.109.0.0/16', '24'],
                'public': ['10.109.0.0/16', '24'],
                'private': ['10.109.0.0/16', '24']},
            nodes_count=10,
            numa_nodes=0,
            second_volume_capacity=50,
            slave_memory=3027,
            slave_vcpu=2,
            slave_volume_capacity=50,
            third_volume_capacity=50,
            use_all_disks=True,
        )
        assert self.c.list_env_names() == ['test', 'test2']

    def test_create_env_from_config(self):
        env = self.c.create_env_from_config(self.conf)
        assert env.name == 'test2'
        assert env.get_address_pool(name='pool1') is not None
        assert env.get_group(name='rack-01') is not None

    def test_create_env_from_config_file(self):
        env = self.c.create_env_from_config('/path/to/my-conf.yaml')
        self.get_conf_mock.assert_called_once_with('/path/to/my-conf.yaml')
        assert env.name == 'test2'
        assert env.get_address_pool(name='pool1') is not None
        assert env.get_group(name='rack-01') is not None

    def test_synchronize_all(self):
        sync_all_mock = self.patch(
            'devops.models.environment.Environment.synchronize_all')

        self.c.synchronize_all()
        sync_all_mock.assert_called_once_with()
