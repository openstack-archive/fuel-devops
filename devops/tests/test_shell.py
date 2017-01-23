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

# pylint: disable=no-self-use

import datetime
import unittest

from dateutil import tz
import mock
import netaddr

from devops import error
from devops import models
from devops import shell


class TestMain(unittest.TestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        super(TestMain, self).setUp()

        self.sys_mock = self.patch('devops.shell.sys')
        self.shell_mock = self.patch('devops.shell.Shell')
        self.shell_inst = self.shell_mock.return_value

    def test_main_sys_args(self):
        self.sys_mock.argv = ['dos.py', 'list']

        shell.main()
        self.shell_mock.assert_called_once_with(['list'])
        self.shell_inst.execute.assert_called_once_with()
        assert self.sys_mock.exit.called is False

    def test_main(self):
        shell.main(['show'])
        self.shell_mock.assert_called_once_with(['show'])
        self.shell_inst.execute.assert_called_once_with()
        assert self.sys_mock.exit.called is False

    def test_main_devops_error(self):
        err = error.DevopsError('my error')
        self.shell_inst.execute.side_effect = err

        shell.main(['start'])
        self.shell_mock.assert_called_once_with(['start'])
        self.shell_inst.execute.assert_called_once_with()
        self.sys_mock.exit.assert_called_once_with('Error: my error')

    def test_main_exception(self):
        err = ValueError('error')
        self.shell_inst.execute.side_effect = err

        with self.assertRaises(ValueError):
            shell.main(['start'])


class TestShell(unittest.TestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        super(TestShell, self).setUp()

        self.print_mock = self.patch('devops.shell.print')
        self.tzlocal_mock = self.patch(
            'devops.helpers.helpers.tz.tzlocal',
            return_value=tz.gettz('Europe/Rome'))

        self.client_mock = self.patch('devops.client.DevopsClient',
                                      autospec=True)
        self.client_inst = self.client_mock.return_value

        def create_snap_mock(name, t):
            m = mock.Mock()
            m.name = name
            m.created = datetime.datetime(2016, 5, 12, 15, 12, t)
            return m

        def create_l2netdev_mock(name):
            m = mock.Mock(spec=models.L2NetworkDevice)
            m.name = name
            return m

        self.l2netdevs = {
            'fuelweb_admin': create_l2netdev_mock('fuelweb_admin'),
            'public': create_l2netdev_mock('public'),
            'storage': create_l2netdev_mock('storage'),
        }

        def create_node_mock(name, vnc_port=5005, snapshots=None):
            m = mock.Mock(spec=models.Node)
            m.name = name
            m.group.name = 'rack-01'
            m.set_vcpu = mock.Mock(return_value=None)
            m.set_memory = mock.Mock(return_value=None)
            m.get_vnc_port = mock.Mock(return_value=vnc_port)
            m.erase_snapshot = mock.Mock(return_value=None)
            snap_mocks = []
            if snapshots:
                snap_mocks = [
                    create_snap_mock(s_name, t) for s_name, t in snapshots]
            m.get_snapshots.return_value = snap_mocks
            return m

        self.nodes = {
            'env1': {
                'admin': create_node_mock('admin', snapshots=[('snap1', 15),
                                                              ('snap2', 16)]),
                'slave-00': create_node_mock('slave-00',
                                             snapshots=[('snap1', 15)]),
                'slave-01': create_node_mock('slave-01'),
            }
        }

        def create_ap_mock(name, ip_network):
            m = mock.Mock(spec=models.AddressPool)
            m.name = name
            m.ip_network = netaddr.IPNetwork(ip_network)
            return m

        self.aps = {
            'env1': [
                create_ap_mock('fuelweb_admin-pool01', '109.10.0.0/24'),
                create_ap_mock('public-pool01', '109.10.1.0/24'),
                create_ap_mock('storage-pool01', '109.10.2.0/24'),
            ]
        }

        def create_env_mock(env_name, created, nodes, aps, admin_ip=None):
            m = mock.Mock(created=created)
            m.name = env_name
            m.get_node.side_effect = lambda name: nodes.get(name)
            m.get_nodes.side_effect = nodes.values
            m.get_address_pools.return_value = aps
            m.get_admin.side_effect = lambda: nodes['admin']
            m.get_admin_ip.return_value = admin_ip
            m.has_admin.side_effect = lambda: bool(admin_ip)
            m.get_env_l2_network_devices = lambda: [{'name': 'fuelweb_admin'}]
            return m

        self.env_mocks = {
            'env1': create_env_mock(
                env_name='env1',
                created=datetime.datetime(2016, 5, 12, 15, 12, 10),
                nodes=self.nodes['env1'], aps=self.aps['env1'],
                admin_ip='109.10.0.2'),
            'env2': create_env_mock(
                env_name='env2',
                created=datetime.datetime(2016, 5, 12, 15, 12, 11),
                nodes={}, aps=[], admin_ip='109.10.1.2'),
            'env3': create_env_mock(
                env_name='env3',
                created=datetime.datetime(2016, 5, 12, 15, 12, 12),
                nodes={}, aps=[]),
        }
        self.client_inst.list_env_names.side_effect = self.env_mocks.keys
        self.client_inst.get_env.side_effect = self.env_mocks.__getitem__

    def test_shell(self):
        sh = shell.Shell(['list'])
        assert sh.args == ['list']
        self.client_mock.assert_called_once_with()

    def test_shell_command_not_create(self):
        sh = shell.Shell(['show', 'env1'])
        assert sh.args == ['show', 'env1']
        self.client_inst.get_env.assert_called_once_with('env1')

    def test_list(self):
        sh = shell.Shell(['list'])
        sh.execute()

        self.print_mock.assert_called_once_with(
            'NAME\n'
            '------\n'
            'env1\n'
            'env2\n'
            'env3')

    def test_list_ips(self):
        sh = shell.Shell(['list', '--ips'])
        sh.execute()

        self.print_mock.assert_called_once_with(
            'NAME    ADMIN IP\n'
            '------  ----------\n'
            'env1    109.10.0.2\n'
            'env2    109.10.1.2\n'
            'env3')

    def test_list_ips_timestamps(self):
        sh = shell.Shell(['list', '--ips', '--timestamps'])
        sh.execute()

        self.print_mock.assert_called_once_with(
            'NAME    ADMIN IP    CREATED\n'
            '------  ----------  -------------------\n'
            'env1    109.10.0.2  2016-05-12_17:12:10\n'
            'env2    109.10.1.2  2016-05-12_17:12:11\n'
            'env3                2016-05-12_17:12:12')

    def test_list_none(self):
        self.env_mocks.clear()

        sh = shell.Shell(['list'])
        assert self.print_mock.called is False
        sh.execute()

        assert self.print_mock.called is False

    def test_show(self):
        sh = shell.Shell(['show', 'env1'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.print_mock.assert_called_once_with(
            '  VNC  NODE-NAME    GROUP-NAME\n'
            '-----  -----------  ------------\n'
            ' 5005  admin        rack-01\n'
            ' 5005  slave-00     rack-01\n'
            ' 5005  slave-01     rack-01')

    def test_show_none(self):
        sh = shell.Shell(['show', 'env2'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env2')
        assert self.print_mock.called is False

    def test_erase(self):
        sh = shell.Shell(['erase', 'env1'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.env_mocks['env1'].erase.assert_called_once_with()

    def test_start(self):
        sh = shell.Shell(['start', 'env1'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.env_mocks['env1'].start.assert_called_once_with()

    def test_destroy(self):
        sh = shell.Shell(['destroy', 'env1'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.env_mocks['env1'].destroy.assert_called_once_with()

    def test_suspend(self):
        sh = shell.Shell(['suspend', 'env1'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.env_mocks['env1'].suspend.assert_called_once_with()

    def test_resume(self):
        sh = shell.Shell(['resume', 'env1'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.env_mocks['env1'].resume.assert_called_once_with()

    def test_revert(self):
        sh = shell.Shell(['revert', 'env1', 'snap1'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.env_mocks['env1'].revert.assert_called_once_with(
            'snap1', flag=False)

    def test_snapshot(self):
        sh = shell.Shell(['snapshot', 'env1', 'snap1'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.env_mocks['env1'].snapshot.assert_called_once_with('snap1')

    def test_sync(self):
        sh = shell.Shell(['sync'])
        sh.execute()

        self.client_inst.synchronize_all.assert_called_once_with()

    def test_snapshot_list(self):
        sh = shell.Shell(['snapshot-list', 'env1'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.print_mock.assert_called_once_with(
            'SNAPSHOT    CREATED              NODES-NAMES\n'
            '----------  -------------------  ---------------\n'
            'snap1       2016-05-12 17:12:15  admin, slave-00\n'
            'snap2       2016-05-12 17:12:16  admin')

    def test_snapshot_list_none(self):
        sh = shell.Shell(['snapshot-list', 'env2'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env2')
        assert self.print_mock.called is False

    def test_snapshot_delete(self):
        sh = shell.Shell(['snapshot-delete', 'env1', 'snap1'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        admin = self.nodes['env1']['admin']
        admin.erase_snapshot.assert_called_once_with(name='snap1')
        slave = self.nodes['env1']['slave-00']
        slave.erase_snapshot.assert_called_once_with(name='snap1')

    def test_net_list(self):
        sh = shell.Shell(['net-list', 'env1'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.print_mock.assert_called_once_with(
            'NETWORK NAME          IP NET\n'
            '--------------------  -------------\n'
            'fuelweb_admin-pool01  109.10.0.0/24\n'
            'public-pool01         109.10.1.0/24\n'
            'storage-pool01        109.10.2.0/24')

    def test_net_list_none(self):
        sh = shell.Shell(['net-list', 'env2'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env2')
        assert self.print_mock.called is False

    def test_time_sync(self):
        self.env_mocks['env1'].get_curr_time.return_value = {
            'node1': 'Thu May 12 18:26:34 MSK 2016',
            'node2': 'Thu May 12 18:13:44 MSK 2016',
        }
        self.env_mocks['env1'].sync_time.return_value = {
            'node1': 'Thu May 12 19:00:00 MSK 2016',
            'node2': 'Thu May 12 19:00:00 MSK 2016',
        }

        sh = shell.Shell(['time-sync', 'env1'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.env_mocks['env1'].get_curr_time.assert_called_once_with(None)
        self.env_mocks['env1'].sync_time.assert_called_once_with(None)

    def test_time_sync_node(self):
        self.env_mocks['env1'].get_curr_time.return_value = {
            'node1': 'Thu May 12 18:26:34 MSK 2016',
        }
        self.env_mocks['env1'].sync_time.return_value = {
            'node1': 'Thu May 12 19:00:00 MSK 2016',
        }

        sh = shell.Shell(['time-sync', 'env1', '--node-name', 'node1'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.env_mocks['env1'].get_curr_time.assert_called_once_with(['node1'])
        self.env_mocks['env1'].sync_time.assert_called_once_with(['node1'])

    def test_revert_resume(self):
        self.env_mocks['env1'].get_curr_time.return_value = {
            'node1': 'Thu May 12 18:26:34 MSK 2016',
            'node2': 'Thu May 12 18:13:44 MSK 2016',
        }
        self.env_mocks['env1'].sync_time.return_value = {
            'node1': 'Thu May 12 19:00:00 MSK 2016',
            'node2': 'Thu May 12 19:00:00 MSK 2016',
        }

        sh = shell.Shell(['revert-resume', 'env1', 'snap1'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.env_mocks['env1'].revert.assert_called_once_with(
            'snap1', flag=False)
        self.env_mocks['env1'].resume.assert_called_once_with()
        self.env_mocks['env1'].get_curr_time.assert_called_once_with(None)
        self.env_mocks['env1'].sync_time.assert_called_once_with(None)

    def test_version(self):
        sh = shell.Shell(['version'])
        sh.execute()

        assert self.print_mock.called

    def test_create(self):
        sh = shell.Shell(
            [
                'create', 'test-env',
                '--net-pool', '10.109.0.0/16:24',
                '--iso-path', '/tmp/my.iso',
                '--admin-vcpu', '4',
                '--admin-ram', '2048',
                '--admin-disk-size', '80',
                '--vcpu', '2',
                '--ram', '512',
                '--node-count', '5',
                '--second-disk-size', '35',
                '--third-disk-size', '45',
            ])
        sh.execute()

        self.client_inst.create_env.assert_called_once_with(
            env_name='test-env',
            admin_iso_path='/tmp/my.iso',
            admin_vcpu=4,
            admin_memory=2048,
            admin_sysvolume_capacity=80,
            nodes_count=5,
            slave_vcpu=2,
            slave_memory=512,
            second_volume_capacity=35,
            third_volume_capacity=45,
            net_pool=['10.109.0.0/16', '24'],
        )

    def test_create_env(self):
        sh = shell.Shell(['create-env', 'myenv.yaml'])
        sh.execute()

        self.client_inst.create_env_from_config.assert_called_once_with(
            'myenv.yaml')

    def test_slave_add(self):
        sh = shell.Shell(
            [
                'slave-add', 'env1',
                '--node-count', '5',
                '--vcpu', '2',
                '--ram', '512',
                '--second-disk-size', '35',
                '--third-disk-size', '45',
            ])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.env_mocks['env1'].add_slaves.assert_called_once_with(
            nodes_count=5,
            slave_vcpu=2,
            slave_memory=512,
            second_volume_capacity=35,
            third_volume_capacity=45,
        )

    def test_slave_remove(self):
        sh = shell.Shell(['slave-remove', 'env1', '-N', 'slave-01'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.nodes['env1']['slave-01'].remove.assert_called_once_with()

    def test_slave_change(self):
        sh = shell.Shell(
            [
                'slave-change', 'env1',
                '-N', 'slave-01',
                '--vcpu', '4',
                '--ram', '256',
            ])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.nodes['env1']['slave-01'].set_vcpu.assert_called_once_with(
            vcpu=4)
        self.nodes['env1']['slave-01'].set_memory.assert_called_once_with(
            memory=256)

    def test_admin_change(self):
        sh = shell.Shell(
            [
                'admin-change', 'env1',
                '--admin-vcpu', '8',
                '--admin-ram', '768',
            ])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.nodes['env1']['admin'].set_vcpu.assert_called_once_with(
            vcpu=8)
        self.nodes['env1']['admin'].set_memory.assert_called_once_with(
            memory=768)

    def test_admin_setup(self):
        group = mock.Mock(spec=models.Group)
        self.env_mocks['env1'].get_groups.return_value = [group]

        sh = shell.Shell(
            [
                'admin-setup', 'env1',
                '--boot-from', 'cdrom',
                '--iface', 'eth1',
            ])
        sh.execute()

        group.start_networks.assert_called_once_with()
        self.client_inst.get_env.assert_called_once_with('env1')
        self.env_mocks['env1'].admin_setup.assert_called_once_with(
            boot_from='cdrom',
            iface='eth1')

    def test_node_start(self):
        sh = shell.Shell(['node-start', 'env1', '-N', 'slave-01'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.nodes['env1']['slave-01'].start.assert_called_once_with()

    def test_node_destroy(self):
        sh = shell.Shell(['node-destroy', 'env1', '-N', 'slave-01'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.env_mocks['env1'].get_node.assert_called_once_with(
            name='slave-01')
        self.nodes['env1']['slave-01'].destroy.assert_called_once_with()

    def test_node_reset(self):
        sh = shell.Shell(['node-reset', 'env1', '-N', 'slave-01'])
        sh.execute()

        self.client_inst.get_env.assert_called_once_with('env1')
        self.nodes['env1']['slave-01'].reset.assert_called_once_with()
