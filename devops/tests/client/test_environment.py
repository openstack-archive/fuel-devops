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

from devops.client.environment import DevopsEnvironment
from devops.client.nailgun import NailgunClient
from devops import error
from devops.helpers.helpers import wait_tcp
from devops.helpers.ntp import GroupNtpSync
from devops.helpers.ssh_client import SSHAuth
from devops.helpers.ssh_client import SSHClient
from devops.tests.driver.driverless import DriverlessTestCase


class TestDevopsEnvironment(DriverlessTestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        super(TestDevopsEnvironment, self).setUp()
        self.paramiko_mock = self.patch('devops.client.environment.paramiko')
        self.l2dev_start_mock = self.patch(
            'devops.models.network.L2NetworkDevice.start')
        self.vol_define_mock = self.patch(
            'devops.models.volume.Volume.define')
        self.wait_tcp_mock = self.patch(
            'devops.client.environment.wait_tcp', spec=wait_tcp)
        self.ssh_mock = self.patch(
            'devops.client.environment.SSHClient', spec=SSHClient)
        self.nc_mock = self.patch(
            'devops.client.environment.NailgunClient', spec=NailgunClient)
        self.nc_mock_inst = self.nc_mock.return_value
        self.mac_to_ip = {
            '64:52:dc:96:12:cc': '10.109.0.100',
        }
        self.nc_mock_inst.get_slave_ip_by_mac.side_effect = self.mac_to_ip.get

        self.ntpgroup_mock = self.patch(
            'devops.client.environment.GroupNtpSync', spec=GroupNtpSync)
        self.ntpgroup_inst = self.ntpgroup_mock.return_value

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
            'devops.client.environment.create_slave_config')
        self.cr_sl_conf_mock.return_value = self.slave_conf

        self.ext_mock = self.patch(
            'devops.models.node.Node.ext')

        self.env.add_group(group_name='default',
                           driver_name='devops.driver.empty')

        self.denv = DevopsEnvironment(self.env)

    def test_add_slaves(self):
        nodes = self.denv.add_slaves(
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
        self.group.add_node(
            name='admin',
            role='fule_master')

        admin = self.denv.admin_setup()

        assert admin is not None
        self.ext_mock.get_kernel_cmd.assert_called_once_with(
            boot_from='cdrom',
            wait_for_external_config='no',
            iface='enp0s3')
        self.ext_mock.bootstrap_and_wait()
        self.ext_mock.deploy_wait()

    def test_get_active_nodes(self):
        assert self.denv.get_active_nodes() == []

        self.group.add_node(
            name='admin',
            role='fule_master')
        self.patch('devops.models.node.Node.is_active', return_value=True)
        nodes = self.denv.get_active_nodes()
        assert len(nodes) == 1
        assert nodes[0].name == 'admin'

    def test_get_admin(self):
        with self.assertRaises(error.DevopsError):
            self.denv.get_admin()

        self.group.add_node(
            name='admin',
            role='fule_master')

        node = self.denv.get_admin()
        assert node is not None
        assert node.name == 'admin'

    def test_get_admin_ip(self):
        self.group.add_node(
            name='admin',
            role='fule_master',
            interfaces=[dict(
                label='eth0',
                l2_network_device='admin',
                interface_model='e1000',
            )])

        ip = self.denv.get_admin_ip()
        assert ip == '10.109.0.2'

    def test_get_admin_remote(self):
        ssh_client = self.ssh_mock.return_value
        self.group.add_node(
            name='admin',
            role='fule_master',
            interfaces=[dict(
                label='eth0',
                l2_network_device='admin',
                interface_model='e1000',
            )])

        remote = self.denv.get_admin_remote()
        assert remote is ssh_client
        self.ssh_mock.assert_called_once_with(
            '10.109.0.2', auth=SSHAuth(username='root', password='r00tme'))

        self.wait_tcp_mock.assert_called_once_with(
            host='10.109.0.2', port=22, timeout=180,
            timeout_msg='Admin node 10.109.0.2 is not accessible by SSH.')

    def test_get_node_ip(self):
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

        ip = self.denv.get_node_ip('slave-00')
        assert ip == '10.109.0.100'

    def test_get_private_keys(self):
        ssh_client = self.ssh_mock.return_value.__enter__.return_value
        ssh_client.open = mock.mock_open()
        key = self.paramiko_mock.RSAKey.from_private_key.return_value

        self.group.add_node(
            name='admin',
            role='fule_master',
            interfaces=[dict(
                label='eth0',
                l2_network_device='admin',
                interface_model='e1000',
            )])

        keys = self.denv.get_private_keys()
        assert len(keys) == 2
        assert keys == [key, key]

        self.ssh_mock.assert_called_once_with(
            '10.109.0.2', auth=SSHAuth(username='root', password='r00tme'))
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
        remote = self.denv.get_node_remote('slave-00')
        assert remote is ssh_client
        self.ssh_mock.assert_called_with(
            '10.109.0.100', auth=SSHAuth(username='root', password='r00tme',
                                         keys=keys))

        self.wait_tcp_mock.assert_called_with(
            host='10.109.0.2', port=22, timeout=180,
            timeout_msg='Admin node 10.109.0.2 is not accessible by SSH.')

    def test_sync_time(self):
        ssh_client = self.ssh_mock.return_value
        self.patch('devops.models.node.Node.is_active', return_value=True)

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

        t = self.denv.sync_time()
        assert t is self.ntpgroup_inst.get_curr_time.return_value

        self.ntpgroup_mock.assert_called_once_with()
        self.ntpgroup_inst.add_node.assert_has_calls((
            mock.call(ssh_client, 'admin'),
            mock.call(ssh_client, 'slave-00'),
        ))

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

        t = self.denv.get_curr_time(node_names=['admin', 'slave-00'])
        assert t is self.ntpgroup_inst.get_curr_time.return_value

        self.ntpgroup_mock.assert_called_once_with()
        self.ntpgroup_inst.add_node.assert_has_calls((
            mock.call(ssh_client, 'admin'),
            mock.call(ssh_client, 'slave-00'),
        ))

        assert self.ntpgroup_inst.sync_time.call_count == 0
        self.ntpgroup_inst.get_curr_time.assert_called_once_with()
        self.ntpgroup_inst.__enter__.assert_called_once_with()
        self.ntpgroup_inst.__exit__.assert_called_once_with(None, None, None)

    def test_get_default_gw(self):
        assert self.denv.get_default_gw() == '10.109.0.1'
        assert self.denv.get_default_gw('public') == '10.109.1.1'

    def test_get_admin_login(self):
        assert self.denv.get_admin_login() == 'root'
