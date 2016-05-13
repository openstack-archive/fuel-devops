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

from devops.client import DevopsClient
from devops.client import NailgunClient
from devops.error import DevopsError
from devops.helpers.helpers import wait_tcp
from devops.helpers.ntp import NtpGroup
from devops.helpers.ssh_client import SSHClient
from devops.tests.driver.driverless import DriverlessTestCase


class TestDevopsClient(DriverlessTestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        super(TestDevopsClient, self).setUp()
        self.paramiko_mock = self.patch('devops.client.paramiko')
        self.l2dev_start_mock = self.patch(
            'devops.models.network.L2NetworkDevice.start')
        self.vol_define_mock = self.patch(
            'devops.models.volume.Volume.define')
        self.wait_tcp_mock = self.patch('devops.client.wait_tcp',
                                        spec=wait_tcp)
        self.ssh_mock = self.patch('devops.client.SSHClient', spec=SSHClient)
        self.nc_mock = self.patch('devops.client.NailgunClient',
                                  spec=NailgunClient)
        self.nc_mock_inst = self.nc_mock.return_value
        self.mac_to_ip = {
            '64:52:dc:96:12:cc': '10.109.0.100',
        }
        self.nc_mock_inst.get_slave_ip_by_mac.side_effect = self.mac_to_ip.get

        self.ntpgroup_mock = self.patch('devops.client.NtpGroup',
                                        spec=NtpGroup)
        self.ntpgroup_inst = self.ntpgroup_mock.return_value

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
                                'name': 'devops.models',
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
            'devops.client.create_devops_config')
        self.cr_conf_mock.return_value = self.conf

        self.slave_conf = {
            'name': 'slave-00',
            'role': 'fuel_slave',
            'params': {},
            'volumes': [
                {
                    'name': 'system',
                },
            ]
        }

        self.cr_sl_conf_mock = self.patch(
            'devops.client.create_slave_config')
        self.cr_sl_conf_mock.return_value = self.slave_conf

        self.ext_mock = self.patch(
            'devops.models.node.Node.ext')

        self.env.add_group(group_name='default',
                           driver_name='devops.models')

        self.c = DevopsClient()

    def test_env(self):
        assert self.c.env is None

        self.c.select_env(name='test')

        assert self.c.env is not None
        assert self.c.env.name == 'test'

        with self.assertRaises(DevopsError):
            self.c.select_env('unknown')

        assert self.c.env is None

    def test_create_env_from_config(self):
        env = self.c.create_env_from_config(self.conf)

        assert env is not None
        assert env.name == 'test2'
        self.l2dev_start_mock.assert_called_once_with()

    def test_create_env(self):
        self.cr_conf_mock.return_value = self.conf
        env = self.c.create_env(
            env_name='test2',
            nodes_count=1,
            admin_iso_path='/tmp/my.iso')

        self.cr_conf_mock.assert_called_once_with(
            boot_from='cdrom',
            env_name='test2',
            admin_vcpu=2,
            admin_memory=3072,
            admin_sysvolume_capacity=75,
            admin_iso_path='/tmp/my.iso',
            nodes_count=1,
            numa_nodes=0,
            slave_vcpu=2,
            slave_memory=3027,
            slave_volume_capacity=50,
            second_volume_capacity=50,
            third_volume_capacity=50,
            use_all_disks=True,
            ironic_nodes_count=0,
            networks_bonding=False,
            networks_bondinginterfaces={
                'public': ['eth2', 'eth3', 'eth4', 'eth5'],
                'admin': ['eth0', 'eth1']},
            networks_multiplenetworks=False,
            networks_nodegroups=(),
            networks_interfaceorder=[
                'admin', 'public', 'management', 'private', 'storage'],
            networks_pools={
                'storage': ['10.109.0.0/16', '24'],
                'public': ['10.109.0.0/16', '24'],
                'management': ['10.109.0.0/16', '24'],
                'admin': ['10.109.0.0/16', '24'],
                'private': ['10.109.0.0/16', '24']},
            networks_forwarding={
                'storage': None,
                'public': 'nat',
                'management': None,
                'admin': 'nat',
                'private': None},
            networks_dhcp={
                'storage': False,
                'public': False,
                'management': False,
                'admin': False,
                'private': False},
            driver_enable_acpi=False,
        )

        assert env is not None
        assert env.name == 'test2'
        self.l2dev_start_mock.assert_called_once_with()

    def test_add_slaves(self):
        self.c.select_env(name='test')

        nodes = self.c.add_slaves(
            nodes_count=1)

        self.cr_sl_conf_mock.assert_called_once_with(
            slave_name='slave-00',
            slave_role='fuel_slave',
            slave_vcpu=1,
            slave_memory=1024,
            slave_volume_capacity=50,
            second_volume_capacity=50,
            third_volume_capacity=50,
            interfaceorder=[
                'admin', 'public', 'management', 'private', 'storage'],
            numa_nodes=0,
            use_all_disks=True,
            networks_multiplenetworks=False,
            networks_nodegroups=(),
            networks_bonding=False,
            networks_bondinginterfaces={
                'admin': ['eth0', 'eth1'],
                'public': ['eth2', 'eth3', 'eth4', 'eth5']},
        )

        assert len(nodes) == 1
        assert nodes[0].name == 'slave-00'

        self.vol_define_mock.assert_called_once_with()

    def test_admin_setup(self):
        self.c.select_env(name='test')
        self.group.add_node(
            name='admin',
            role='fule_master')

        admin = self.c.admin_setup()

        assert admin is not None
        self.ext_mock.get_kernel_cmd.assert_called_once_with(
            boot_from='cdrom',
            wait_for_external_config='no',
            iface='enp0s3')
        self.ext_mock.bootstrap_and_wait()
        self.ext_mock.deploy_wait()

    def test_get_active_nodes(self):
        self.c.select_env(name='test')

        assert self.c.get_active_nodes() == []

        self.group.add_node(
            name='admin',
            role='fule_master')
        self.patch('devops.models.node.Node.is_active', return_value=True)
        nodes = self.c.get_active_nodes()
        assert len(nodes) == 1
        assert nodes[0].name == 'admin'

    def test_get_admin(self):
        self.c.select_env(name='test')
        self.group.add_node(
            name='admin',
            role='fule_master')

        node = self.c.get_admin()
        assert node is not None
        assert node.name == 'admin'

    def test_get_admin_ip(self):
        self.c.select_env(name='test')
        self.group.add_node(
            name='admin',
            role='fule_master',
            interfaces=[dict(
                label='eth0',
                l2_network_device='admin',
                interface_model='e1000',
            )])

        ip = self.c.get_admin_ip()
        assert ip == '10.109.0.2'

    def test_get_admin_remote(self):
        ssh_client = self.ssh_mock.return_value
        self.c.select_env(name='test')
        self.group.add_node(
            name='admin',
            role='fule_master',
            interfaces=[dict(
                label='eth0',
                l2_network_device='admin',
                interface_model='e1000',
            )])

        remote = self.c.get_admin_remote()
        assert remote is ssh_client
        self.ssh_mock.assert_called_once_with(
            '10.109.0.2', username='root', password='r00tme')

        self.wait_tcp_mock.assert_called_once_with(
            host='10.109.0.2', port=22, timeout=180,
            timeout_msg='Admin node 10.109.0.2 is not accessible by SSH.')

    def test_get_node_ip(self):
        self.c.select_env(name='test')
        self.group.add_node(
            name='admin',
            role='fule_master',
            interfaces=[dict(
                label='eth0',
                l2_network_device='admin',
                interface_model='e1000',
            )])

        slave = self.group.add_node(
            name='slave-00',
            role='fule_slave',
            interfaces=[dict(
                label='eth0',
                l2_network_device='admin',
                interface_model='e1000',
            )])

        eth0 = slave.get_interface_by_network_name('admin')
        eth0.mac_address = '64:52:dc:96:12:cc'
        eth0.save()

        ip = self.c.get_node_ip('slave-00')
        assert ip == '10.109.0.100'

    def test_get_private_keys(self):
        ssh_client = self.ssh_mock.return_value
        ssh_client.open = mock.mock_open()
        key = self.paramiko_mock.RSAKey.from_private_key.return_value
        self.c.select_env(name='test')
        self.group.add_node(
            name='admin',
            role='fule_master',
            interfaces=[dict(
                label='eth0',
                l2_network_device='admin',
                interface_model='e1000',
            )])

        keys = self.c.get_private_keys()
        assert len(keys) == 2
        assert keys == [key, key]

        self.ssh_mock.assert_called_once_with(
            '10.109.0.2', username='root', password='r00tme')
        assert ssh_client.isfile.call_count == 2
        ssh_client.isfile.assert_any_call('/root/.ssh/id_rsa')
        ssh_client.isfile.assert_any_call('/root/.ssh/bootstrap.rsa')
        assert ssh_client.open.call_count == 2
        ssh_client.open.assert_any_call('/root/.ssh/id_rsa')
        ssh_client.open.assert_any_call('/root/.ssh/bootstrap.rsa')

        assert self.paramiko_mock.RSAKey.from_private_key.call_count == 2
        self.paramiko_mock.RSAKey.from_private_key.assert_called_with(
            ssh_client.open.return_value)

    def test_get_node_remote(self):
        ssh_client = self.ssh_mock.return_value
        ssh_client.open = mock.mock_open()
        self.c.select_env(name='test')
        self.group.add_node(
            name='admin',
            role='fule_master',
            interfaces=[dict(
                label='eth0',
                l2_network_device='admin',
                interface_model='e1000',
            )])

        slave = self.group.add_node(
            name='slave-00',
            role='fule_slave',
            interfaces=[dict(
                label='eth0',
                l2_network_device='admin',
                interface_model='e1000',
            )])

        eth0 = slave.get_interface_by_network_name('admin')
        eth0.mac_address = '64:52:dc:96:12:cc'
        eth0.save()

        key = self.paramiko_mock.RSAKey.from_private_key.return_value
        keys = [key, key]
        remote = self.c.get_node_remote('slave-00')
        assert remote is ssh_client
        self.ssh_mock.assert_called_with(
            '10.109.0.100', username='root', password='r00tme',
            private_keys=keys)

        self.wait_tcp_mock.assert_called_with(
            host='10.109.0.2', port=22, timeout=180,
            timeout_msg='Admin node 10.109.0.2 is not accessible by SSH.')

    def test_timesync(self):
        ssh_client = self.ssh_mock.return_value
        self.patch('devops.models.node.Node.is_active', return_value=True)
        self.c.select_env(name='test')
        self.group.add_node(
            name='admin',
            role='fule_master',
            interfaces=[dict(
                label='eth0',
                l2_network_device='admin',
                interface_model='e1000',
            )])
        slave = self.group.add_node(
            name='slave-00',
            role='fule_slave',
            interfaces=[dict(
                label='eth0',
                l2_network_device='admin',
                interface_model='e1000',
            )])

        eth0 = slave.get_interface_by_network_name('admin')
        eth0.mac_address = '64:52:dc:96:12:cc'
        eth0.save()

        t = self.c.timesync(node_names=['admin', 'slave-00'])
        assert t is self.ntpgroup_inst.get_curr_time.return_value

        self.ntpgroup_mock.assert_called_once_with()
        assert self.ntpgroup_inst.add_node.call_count == 2
        self.ntpgroup_inst.add_node.assert_any_call(
            ssh_client, 'admin', '10.109.0.2')
        self.ntpgroup_inst.add_node.assert_any_call(
            ssh_client, 'slave-00', '10.109.0.2')

        assert self.ntpgroup_inst.sync_time.call_count == 3
        self.ntpgroup_inst.sync_time.assert_any_call('admin')
        self.ntpgroup_inst.sync_time.assert_any_call('pacemaker')
        self.ntpgroup_inst.sync_time.assert_any_call('other')
        self.ntpgroup_inst.get_curr_time.assert_called_once_with()
        self.ntpgroup_inst.__enter__.assert_called_once_with()
        self.ntpgroup_inst.__exit__.assert_called_once_with(None, None, None)

    def test_get_curr_time(self):
        ssh_client = self.ssh_mock.return_value
        self.patch('devops.models.node.Node.is_active', return_value=True)
        self.c.select_env(name='test')
        self.group.add_node(
            name='admin',
            role='fule_master',
            interfaces=[dict(
                label='eth0',
                l2_network_device='admin',
                interface_model='e1000',
            )])
        slave = self.group.add_node(
            name='slave-00',
            role='fule_slave',
            interfaces=[dict(
                label='eth0',
                l2_network_device='admin',
                interface_model='e1000',
            )])

        eth0 = slave.get_interface_by_network_name('admin')
        eth0.mac_address = '64:52:dc:96:12:cc'
        eth0.save()

        t = self.c.get_curr_time(node_names=['admin', 'slave-00'])
        assert t is self.ntpgroup_inst.get_curr_time.return_value

        self.ntpgroup_mock.assert_called_once_with()
        assert self.ntpgroup_inst.add_node.call_count == 2
        self.ntpgroup_inst.add_node.assert_any_call(
            ssh_client, 'admin', '10.109.0.2')
        self.ntpgroup_inst.add_node.assert_any_call(
            ssh_client, 'slave-00', '10.109.0.2')

        assert self.ntpgroup_inst.sync_time.call_count == 0
        self.ntpgroup_inst.get_curr_time.assert_called_once_with()
        self.ntpgroup_inst.__enter__.assert_called_once_with()
        self.ntpgroup_inst.__exit__.assert_called_once_with(None, None, None)


class TestNailgunClient(TestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        super(TestNailgunClient, self).setUp()

        self.v2pass_mock = self.patch('devops.client.V2Password',
                                      spec=V2Password)
        self.v2pass_inst = self.v2pass_mock.return_value
        self.ks_session_mock = self.patch('devops.client.KeystoneSession',
                                          spec=KeystoneSession)
        self.k2_session_inst = self.ks_session_mock.return_value
        self.nodes_mock = self.k2_session_inst.get.return_value

        self.nc = NailgunClient('10.109.0.2')

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

        with self.assertRaises(DevopsError):
            self.nc.get_slave_ip_by_mac('a1a1a1a1a1a1')
