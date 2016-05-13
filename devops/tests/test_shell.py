# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

from datetime import datetime as dt
import unittest

import mock
from netaddr import IPNetwork

from devops.client import DevopsClient
from devops.error import DevopsError
from devops import models
from devops.shell import main
from devops.shell import Shell


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

        main()
        self.shell_mock.assert_called_once_with(['list'])
        self.shell_inst.execute.assert_called_once_with()
        assert self.sys_mock.exit.called is False

    def test_main(self):
        main(['show'])
        self.shell_mock.assert_called_once_with(['show'])
        self.shell_inst.execute.assert_called_once_with()
        assert self.sys_mock.exit.called is False

    def test_main_devops_error(self):
        error = DevopsError('error')
        self.shell_inst.execute.side_effect = error

        main(['start'])
        self.shell_mock.assert_called_once_with(['start'])
        self.shell_inst.execute.assert_called_once_with()
        self.sys_mock.exit.assert_called_once_with(error)

    def test_main_exception(self):
        error = ValueError('error')
        self.shell_inst.execute.side_effect = error

        with self.assertRaises(ValueError):
            main(['start'])


class TestShell(unittest.TestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        super(TestShell, self).setUp()

        self.print_mock = self.patch('devops.shell.print')

        self.client_mock = self.patch('devops.shell.DevopsClient',
                                      spec=DevopsClient)
        self.client_inst = self.client_mock.return_value

        self.admin_ips = {
            'env1': '109.10.0.2',
            'env2': '109.10.1.2',
        }

        def create_snap_mock(name, t):
            m = mock.Mock()
            m.name = name
            m.created = dt(2016, 5, 12, 15, 12, t)
            return m

        def create_node_mock(name, vnc_port=5005, snapshots=None):
            m = mock.Mock(spec=models.Node)
            m.name = name
            m.set_vcpu = mock.Mock(return_value=None)
            m.set_memory = mock.Mock(return_value=None)
            m.get_vnc_port = mock.Mock(return_value=vnc_port)
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
            m.ip_network = ip_network
            return m

        self.aps = {
            'env1': [
                create_ap_mock('fuelweb_admin-pool01',
                               IPNetwork('109.10.0.0/24')),
                create_ap_mock('public-pool01', IPNetwork('109.10.1.0/24')),
                create_ap_mock('storage-pool01', IPNetwork('109.10.2.0/24')),
            ]
        }

        def create_env_mock(env_name, created):
            m = mock.Mock(spec=models.Environment, created=created)
            m.name = env_name
            m.get_node.side_effect = \
                lambda name: self.nodes.get(env_name, {}).get(name)
            m.get_nodes.side_effect = \
                lambda: self.nodes.get(env_name, {}).values()
            m.get_address_pools.side_effect = \
                lambda: self.aps.get(env_name, [])
            return m

        self.env_mocks = {
            'env1': create_env_mock(
                env_name='env1', created=dt(2016, 5, 12, 15, 12, 10)),
            'env2': create_env_mock(
                env_name='env2', created=dt(2016, 5, 12, 15, 12, 11)),
            'env3': create_env_mock(
                env_name='env3', created=dt(2016, 5, 12, 15, 12, 12)),
        }
        self.client_inst.list_env_names.side_effect = self.env_mocks.keys
        self.curr_env = None
        self.client_inst.select_env.side_effect = \
            lambda name: setattr(self, 'curr_env', name)
        self.client_inst.get_admin.side_effect = \
            lambda: self.nodes.get(self.curr_env, {}).get('admin')
        self.client_inst.get_admin_ip.side_effect = \
            lambda: self.admin_ips[self.curr_env]
        self.client_inst.has_admin.side_effect = \
            lambda: self.curr_env in self.admin_ips
        type(self.client_inst).env = mock.PropertyMock(
            side_effect=lambda: self.env_mocks[self.curr_env])

    def test_shell(self):
        shell = Shell(['list'])
        assert shell.args == ['list']
        self.client_mock.assert_called_once_with()
        assert shell.env is None

    def test_shell_create(self):
        shell = Shell(['show', 'env1'])
        assert shell.args == ['show', 'env1']
        self.client_mock.assert_called_once_with()
        self.client_inst.select_env.assert_called_once_with(name='env1')
        assert shell.env is self.env_mocks['env1']

    def test_list(self):
        shell = Shell(['list'])
        shell.execute()

        self.print_mock.assert_called_once_with(
            'NAME\n'
            '------\n'
            'env1\n'
            'env2\n'
            'env3')

    def test_list_ips(self):
        shell = Shell(['list', '--ips'])
        shell.execute()

        self.print_mock.assert_called_once_with(
            'NAME    ADMIN IP\n'
            '------  ----------\n'
            'env1    109.10.0.2\n'
            'env2    109.10.1.2\n'
            'env3')

    def test_list_ips_timestamps(self):
        shell = Shell(['list', '--ips', '--timestamps'])
        shell.execute()

        self.print_mock.assert_called_once_with(
            'NAME    ADMIN IP    CREATED\n'
            '------  ----------  -------------------\n'
            'env1    109.10.0.2  2016-05-12_15:12:10\n'
            'env2    109.10.1.2  2016-05-12_15:12:11\n'
            'env3                2016-05-12_15:12:12')

    def test_list_none(self):
        self.env_mocks.clear()

        shell = Shell(['list'])
        self.client_mock.assert_called_once_with()
        shell.execute()

        assert self.print_mock.called is False

    def test_show(self):
        shell = Shell(['show', 'env1'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.print_mock.assert_called_once_with(
            '  VNC  NODE-NAME\n'
            '-----  -----------\n'
            ' 5005  admin\n'
            ' 5005  slave-00\n'
            ' 5005  slave-01')

    def test_show_none(self):
        shell = Shell(['show', 'env2'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env2')
        assert self.print_mock.called is False

    def test_erase(self):
        shell = Shell(['erase', 'env1'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.env_mocks['env1'].erase.assert_called_once_with()

    def test_start(self):
        shell = Shell(['start', 'env1'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.env_mocks['env1'].start.assert_called_once_with()

    def test_destroy(self):
        shell = Shell(['destroy', 'env1'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.env_mocks['env1'].destroy.assert_called_once_with()

    def test_suspend(self):
        shell = Shell(['suspend', 'env1'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.env_mocks['env1'].suspend.assert_called_once_with()

    def test_resume(self):
        shell = Shell(['resume', 'env1'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.env_mocks['env1'].resume.assert_called_once_with()

    def test_revert(self):
        shell = Shell(['revert', 'env1', 'snap1'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.env_mocks['env1'].revert.assert_called_once_with(
            'snap1', flag=False)

    def test_snapshot(self):
        shell = Shell(['snapshot', 'env1', 'snap1'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.env_mocks['env1'].snapshot.assert_called_once_with('snap1')

    def test_sync(self):
        shell = Shell(['sync'])
        shell.execute()

        assert self.client_inst.select_env.called is False
        self.client_inst.synchronize_all.assert_called_once_with()

    def test_snapshot_list(self):
        shell = Shell(['snapshot-list', 'env1'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.print_mock.assert_called_once_with(
            'SNAPSHOT    CREATED              NODES-NAMES\n'
            '----------  -------------------  ---------------\n'
            'snap1       2016-05-12 15:12:15  admin, slave-00\n'
            'snap2       2016-05-12 15:12:16  admin')

    def test_snapshot_list_none(self):
        shell = Shell(['snapshot-list', 'env2'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env2')
        assert self.print_mock.called is False

    def test_net_list(self):
        shell = Shell(['net-list', 'env1'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.print_mock.assert_called_once_with(
            'NETWORK NAME          IP NET\n'
            '--------------------  -------------\n'
            'fuelweb_admin-pool01  109.10.0.0/24\n'
            'public-pool01         109.10.1.0/24\n'
            'storage-pool01        109.10.2.0/24')

    def test_net_list_none(self):
        shell = Shell(['net-list', 'env2'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env2')
        assert self.print_mock.called is False

    def test_time_sync(self):
        self.client_inst.get_curr_time.return_value = {
            'node1': 'Thu May 12 18:26:34 MSK 2016',
            'node2': 'Thu May 12 18:13:44 MSK 2016',
        }
        self.client_inst.timesync.return_value = {
            'node1': 'Thu May 12 19:00:00 MSK 2016',
            'node2': 'Thu May 12 19:00:00 MSK 2016',
        }

        shell = Shell(['time-sync', 'env1'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.client_inst.get_curr_time.assert_called_once_with(None)
        self.client_inst.timesync.assert_called_once_with(None)

    def test_time_sync_node(self):
        self.client_inst.get_curr_time.return_value = {
            'node1': 'Thu May 12 18:26:34 MSK 2016',
        }
        self.client_inst.timesync.return_value = {
            'node1': 'Thu May 12 19:00:00 MSK 2016',
        }

        shell = Shell(['time-sync', 'env1', '--node-name', 'node1'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.client_inst.get_curr_time.assert_called_once_with('node1')
        self.client_inst.timesync.assert_called_once_with('node1')

    def test_revert_resume(self):
        self.client_inst.get_curr_time.return_value = {
            'node1': 'Thu May 12 18:26:34 MSK 2016',
            'node2': 'Thu May 12 18:13:44 MSK 2016',
        }
        self.client_inst.timesync.return_value = {
            'node1': 'Thu May 12 19:00:00 MSK 2016',
            'node2': 'Thu May 12 19:00:00 MSK 2016',
        }

        shell = Shell(['revert-resume', 'env1', 'snap1'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.env_mocks['env1'].revert.assert_called_once_with(
            'snap1', flag=False)
        self.env_mocks['env1'].resume.assert_called_once_with()
        self.client_inst.get_curr_time.assert_called_once_with(None)
        self.client_inst.timesync.assert_called_once_with(None)

    def test_version(self):
        shell = Shell(['version'])
        shell.execute()

        assert self.print_mock.called

    def test_create(self):
        shell = Shell(['create', 'test-env',
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
        shell.execute()

        assert self.client_inst.select_env.called is False
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
            net_pool='10.109.0.0/16:24',
        )

    def test_create_env(self):
        shell = Shell(['create-env', 'myenv.yaml'])
        shell.execute()

        assert self.client_inst.select_env.called is False
        self.client_inst.create_env_from_config.assert_called_once_with(
            'myenv.yaml')

    def test_slave_add(self):
        shell = Shell(['slave-add', 'env1',
                       '--node-count', '5',
                       '--vcpu', '2',
                       '--ram', '512',
                       '--second-disk-size', '35',
                       '--third-disk-size', '45',
                       ])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.client_inst.add_slaves.assert_called_once_with(
            nodes_count=5,
            slave_vcpu=2,
            slave_memory=512,
            second_volume_capacity=35,
            third_volume_capacity=45,
        )

    def test_slave_remove(self):
        shell = Shell(['slave-remove', 'env1', '-N', 'slave-01'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.nodes['env1']['slave-01'].remove.assert_called_once_with()

    def test_slave_change(self):
        shell = Shell(['slave-change', 'env1',
                       '-N', 'slave-01',
                       '--vcpu', '4',
                       '--ram', '256',
                       ])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.nodes['env1']['slave-01'].set_vcpu.assert_called_once_with(
            vcpu=4)
        self.nodes['env1']['slave-01'].set_memory.assert_called_once_with(
            memory=256)

    def test_admin_change(self):
        shell = Shell(['admin-change', 'env1',
                       '--admin-vcpu', '8',
                       '--admin-ram', '768',
                       ])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.nodes['env1']['admin'].set_vcpu.assert_called_once_with(
            vcpu=8)
        self.nodes['env1']['admin'].set_memory.assert_called_once_with(
            memory=768)

    def test_admin_setup(self):
        shell = Shell(['admin-setup', 'env1',
                       '--boot-from', 'cdrom',
                       '--iface', 'eth1',
                       ])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.client_inst.admin_setup.assert_called_once_with(
            boot_from='cdrom',
            iface='eth1')

    def test_node_start(self):
        shell = Shell(['node-start', 'env1', '-N', 'slave-01'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.nodes['env1']['slave-01'].start.assert_called_once_with()

    def test_node_destroy(self):
        shell = Shell(['node-destroy', 'env1', '-N', 'slave-01'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.nodes['env1']['slave-01'].destroy.assert_called_once_with()

    def test_node_reset(self):
        shell = Shell(['node-reset', 'env1', '-N', 'slave-01'])
        shell.execute()

        self.client_inst.select_env.assert_called_once_with(name='env1')
        self.nodes['env1']['slave-01'].reset.assert_called_once_with()
