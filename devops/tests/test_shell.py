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

import datetime
import unittest

from dateutil import tz
import mock

from devops import models
from devops import shell


class BaseShellTestCase(unittest.TestCase):

    def execute(self, *args):
        return shell.main(args)


class TestSnaphotList(BaseShellTestCase):

    @mock.patch('devops.helpers.helpers.tz.tzlocal',
                return_value=tz.gettz('Europe/Rome'))
    @mock.patch.object(shell.Shell, 'print_table')
    @mock.patch.object(models.Environment, 'get')
    def test_snapshot_list_order(self, mock_get_env, mock_print, tzlocal_mock):
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
                ('snap_3', '2015-11-28 01:00:00', 'node, node'),
                ('snap_2', '2015-11-29 01:00:00', 'node, node'),
                ('snap_1', '2015-11-30 01:00:00', 'node, node'),
                ('snap_0', '2015-12-01 01:00:00', 'node, node')
            ],
            headers=('SNAPSHOT', 'CREATED', 'NODES-NAMES')
        )


class TestDoSnapshot(BaseShellTestCase):
    @mock.patch('devops.models.environment.time.time')
    @mock.patch.object(models.Environment, 'get_nodes')
    @mock.patch.object(models.Environment, 'get')
    @mock.patch.object(models.Environment, 'has_snapshot')
    def test_create_snaphot_with_mandatory_snapshot_name(self,
                                                         mock_has_snapshot,
                                                         mock_get_env,
                                                         mock_get_nodes,
                                                         mock_time):
        mock_has_snapshot.return_value = False
        mock_get_env.return_value = models.Environment()
        mock_time.return_value = 123456.789

        nodes = (mock.Mock(), mock.Mock())
        mock_get_nodes.return_value = nodes

        self.execute('snapshot', 'some-env', 'test-snapshot-name')

        for node in nodes:
            node.snapshot.assert_called_once_with(
                force=mock.ANY, description=mock.ANY,
                name="test-snapshot-name", external=False)
