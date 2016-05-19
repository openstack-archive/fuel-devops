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

import unittest
import mock

from devops import error
from devops.helpers import ntp


class TestNtp(unittest.TestCase):
    @mock.patch('devops.helpers.ntp.logger')
    def test_ntp_init(self, logger):
        class Remote(object):
            def __init__(self):
                self.execute = mock.Mock(return_value={'stdout': ['0 2 4']})

            def __repr__(self):
                return self.__class__.__name__

        remote = Remote()
        ntp_init = ntp.NtpInitscript(remote)
        self.assertEqual(ntp_init.remote, remote)
        self.assertEqual(ntp_init.node_name, 'node')
        self.assertIsNone(ntp_init.admin_ip)
        self.assertFalse(ntp_init.is_pacemaker)
        self.assertFalse(ntp_init.is_synchronized)
        self.assertFalse(ntp_init.is_connected)
        self.assertEqual(ntp_init.server, '0 2 4')
        remote.execute.assert_has_calls((
            mock.call(
                "awk '/^server/ && $2 !~ /127.*/ {print $2}' /etc/ntp.conf"),
            mock.call("find /etc/init.d/ -regex '/etc/init.d/ntp.?'")
        ))
        self.assertEqual(
            str(ntp_init),
            'NtpInitscript(remote=Remote, node_name=node, admin_ip=None)')

        remote.execute.reset_mock()
        remote.execute.return_value = {'stdout': ['0 2 4', '1', '2', '3']}

        peers = ntp_init.peers
        self.assertEqual(peers, ['2', '3'])
        remote.execute.assert_called_once_with('ntpq -pn 127.0.0.1')

        remote.execute.reset_mock()
        remote.execute.return_value = {'stdout': ['0 2 4']}

        date = ntp_init.date
        self.assertEqual(date, ['0 2 4'])
        remote.execute.assert_called_once_with('date')

        remote.execute.reset_mock()
        remote.execute.return_value = {'stdout': ['0 2 4', '1', '2', '3']}

        ntp_init.start()
        self.assertFalse(ntp_init.is_connected)
        remote.execute.assert_called_once_with('0 2 4 start')

        remote.execute.reset_mock()
        remote.execute.return_value = {'stdout': ['0 2 4', '1', '2', '3']}

        ntp_init.stop()
        self.assertFalse(ntp_init.is_connected)
        remote.execute.assert_called_once_with('0 2 4 stop')

        remote.execute.reset_mock()
        remote.execute.return_value = {'stdout': ['0 2 4', '1', '2', '3']}

        with mock.patch('devops.helpers.ntp.wait') as wait:
            result = ntp_init.set_actual_time()
            self.assertTrue(result)
            self.assertTrue(ntp_init.is_synchronized)

            wait.assert_called_once()
            remote.execute.assert_called_once_with("hwclock -w")

            wait.reset_mock()
            logger.reset_mock()
            debug = mock.Mock()
            logger.attach_mock(debug, 'debug')

            wait.side_effect = error.TimeoutError('E')
            result = ntp_init.set_actual_time()
            self.assertFalse(result)
            self.assertFalse(ntp_init.is_synchronized)
            debug.assert_called_once_with('Time sync failed with E')

        with mock.patch('time.time', return_value=1) as time:
            result = ntp_init.wait_peer(timeout=-1)
            self.assertFalse(result)
            self.assertFalse(ntp_init.is_connected)
            time.assert_has_calls((mock.call(), mock.call()))

    def test_ntp_pacemaker(self):
        class Remote(object):
            def __init__(self):
                self.execute = mock.Mock(return_value={'stdout': ['0 2 4']})

            def __repr__(self):
                return self.__class__.__name__

        remote = Remote()
        ntp_pcm = ntp.NtpPacemaker(remote)

        self.assertEqual(ntp_pcm.remote, remote)
        self.assertEqual(ntp_pcm.node_name, 'node')
        self.assertIsNone(ntp_pcm.admin_ip)
        self.assertTrue(ntp_pcm.is_pacemaker)
        self.assertFalse(ntp_pcm.is_synchronized)
        self.assertFalse(ntp_pcm.is_connected)
        self.assertEqual(ntp_pcm.server, '0 2 4')
        remote.execute.assert_called_once_with(
            "awk '/^server/ && $2 !~ /127.*/ {print $2}' /etc/ntp.conf")
        self.assertEqual(
            str(ntp_pcm),
            'NtpPacemaker(remote=Remote, node_name=node, admin_ip=None)')

        remote.execute.reset_mock()
        remote.execute.return_value = {'stdout': ['0 2 4', '1', '2', '3']}

        ntp_pcm.start()
        self.assertFalse(ntp_pcm.is_connected)
        remote.execute.assert_has_calls((
            mock.call('ip netns exec vrouter ip l set dev lo up'),
            mock.call('crm resource start p_ntp')
        ))

        remote.execute.reset_mock()
        remote.execute.return_value = {'stdout': ['0 2 4', '1', '2', '3']}

        ntp_pcm.stop()
        self.assertFalse(ntp_pcm.is_connected)
        remote.execute.assert_called_once_with(
            'crm resource stop p_ntp; killall ntpd')

        remote.execute.reset_mock()
        remote.execute.return_value = {'stdout': ['0 2 4', '1', '2', '3']}

        result = ntp_pcm.get_peers()
        self.assertEqual(result, ['0 2 4', '1', '2', '3'])
        remote.execute.assert_called_once_with(
            'ip netns exec vrouter ntpq -pn 127.0.0.1')

    def test_ntp_systemd(self):
        class Remote(object):
            def __init__(self):
                self.execute = mock.Mock(return_value={'stdout': ['0 2 4']})

            def __repr__(self):
                return self.__class__.__name__

        remote = Remote()
        ntp_sysd = ntp.NtpSystemd(remote)

        self.assertEqual(ntp_sysd.remote, remote)
        self.assertEqual(ntp_sysd.node_name, 'node')
        self.assertIsNone(ntp_sysd.admin_ip)
        self.assertFalse(ntp_sysd.is_pacemaker)
        self.assertFalse(ntp_sysd.is_synchronized)
        self.assertFalse(ntp_sysd.is_connected)
        self.assertEqual(ntp_sysd.server, '0 2 4')
        remote.execute.assert_called_once_with(
            "awk '/^server/ && $2 !~ /127.*/ {print $2}' /etc/ntp.conf")
        self.assertEqual(
            str(ntp_sysd),
            'NtpSystemd(remote=Remote, node_name=node, admin_ip=None)')

        remote.execute.reset_mock()
        remote.execute.return_value = {'stdout': ['0 2 4', '1', '2', '3']}

        ntp_sysd.start()
        self.assertFalse(ntp_sysd.is_connected)
        remote.execute.assert_called_once_with('systemctl start ntpd')

        remote.execute.reset_mock()
        remote.execute.return_value = {'stdout': ['0 2 4', '1', '2', '3']}

        ntp_sysd.stop()
        self.assertFalse(ntp_sysd.is_connected)
        remote.execute.assert_called_once_with('systemctl stop ntpd')

        remote.execute.reset_mock()
        remote.execute.return_value = {'stdout': ['0 2 4', '1', '2', '3']}

        result = ntp_sysd.get_peers()
        self.assertEqual(result, ['0 2 4', '1', '2', '3'])
        remote.execute.assert_called_once_with('ntpq -pn 127.0.0.1')

