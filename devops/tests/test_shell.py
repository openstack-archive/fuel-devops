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

import datetime

import mock
import pytest

from devops import models
from devops import shell


class BaseShellTestCase(object):

    def execute(self, *args):
        return shell.main(args)


class TestSnaphotList(BaseShellTestCase):

    @mock.patch.object(shell.Shell, 'print_table')
    @mock.patch.object(models.Environment, 'get')
    def test_snapshot_list_order(self, mock_get_env, mock_print):
        snaps = []
        base_date = datetime.datetime(2015, 12, 1)
        for i in range(4):
            snap = mock.Mock()
            snap.name = "snap_{0}".format(i)
            snap.created = base_date - datetime.timedelta(days=i)
            snaps.append(snap)

        node = mock.Mock()
        node.name = "node"
        node.get_snapshots.return_value = snaps

        env = mock_get_env.return_value
        env.get_nodes.return_value = [node, node]

        self.execute('snapshot-list', 'some-env')

        mock_print.assert_called_once_with(
            columns=[
                ('snap_3', '2015-11-28 00:00:00', 'node, node'),
                ('snap_2', '2015-11-29 00:00:00', 'node, node'),
                ('snap_1', '2015-11-30 00:00:00', 'node, node'),
                ('snap_0', '2015-12-01 00:00:00', 'node, node')
            ],
            headers=('SNAPSHOT', 'CREATED', 'NODES-NAMES')
        )


class TestDoSnapshot(BaseShellTestCase):

    @mock.patch('devops.models.environment.time.time')
    @mock.patch.object(models.Environment, 'get_nodes')
    @mock.patch.object(models.Environment, 'get')
    def test_same_snaphot_name_if_not_provided(self, mock_get_env,
                                               mock_get_nodes, mock_time):
        mock_get_env.return_value = models.Environment()
        mock_time.return_value = 123456.789

        nodes = (mock.Mock(), mock.Mock())
        mock_get_nodes.return_value = nodes

        self.execute('snapshot', 'some-env')

        for node in nodes:
            node.snapshot.assert_called_once_with(
                force=mock.ANY, description=mock.ANY, name="123456")


@pytest.mark.xfail(reason="No DB configured")
class TestAdminSetup(BaseShellTestCase):

    @staticmethod
    def _test_admin_setup(mock_libvirt, expected_keys):
        """Check parameters in libvirt's sendKey method"""
        expected_calls = (mock.call().lookupByUUIDString().sendKey(0, 0, [key],
                                                                   1, 0)
                          for key in expected_keys)
        for expected_call in expected_calls:
            assert expected_call in mock_libvirt.mock_calls

    @pytest.mark.django_db
    @pytest.mark.usefixtures('single_admin_node')
    def test_admin_setup_with_fuelmenu(self, mock_libvirt):
        self.execute('admin-setup', '--show-menu', 'test_env')
        # Keys for "showmenu=yes"
        expected_keys = [31, 35, 24, 17, 50, 18, 49, 22, 13, 21, 18, 31]
        self._test_admin_setup(mock_libvirt, expected_keys)

    @pytest.mark.django_db
    @pytest.mark.usefixtures('single_admin_node')
    def test_admin_setup_without_fuelmenu(self, mock_libvirt):
        self.execute('admin-setup', 'test_env')
        # Keys for "showmenu=no"
        expected_keys = [31, 35, 24, 17, 50, 18, 49, 22, 13, 49, 24]
        self._test_admin_setup(mock_libvirt, expected_keys)
