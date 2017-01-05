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

import socket
import unittest

import mock

# pylint: disable=redefined-builtin
# noinspection PyUnresolvedReferences
from six.moves import xrange
# pylint: enable=redefined-builtin

from devops import error
from devops.helpers import exec_result
from devops.helpers import helpers
from devops.helpers import ssh_client


class TestHelpersHelpers(unittest.TestCase):
    @mock.patch(
        'devops.helpers.helpers.tcp_ping', return_value=False, autospec=True)
    def test_get_free_port(self, ping):
        result = helpers.get_free_port()
        self.assertEqual(result, 32000)
        ping.assert_called_once_with('localhost', 32000)

        ping.reset_mock()
        ping.return_value = True
        self.assertRaises(
            error.DevopsError,
            helpers.get_free_port
        )
        ping.assert_has_calls(
            [
                mock.call('localhost', port)
                for port in xrange(32000, 32100)])

    @mock.patch(
        'devops.helpers.subprocess_runner.Subprocess.execute',
        return_value=exec_result.ExecResult(
            cmd="ping -c 1 -W '{timeout:d}' '{host:s}'".format(
                host='127.0.0.1', timeout=1,
            ),
            exit_code=0,
        )
    )
    def test_icmp_ping(self, caller):
        host = '127.0.0.1'
        timeout = 1
        result = helpers.icmp_ping(host=host)
        caller.assert_called_once_with(
            "ping -c 1 -W '{timeout:d}' '{host:s}'".format(
                host=host, timeout=timeout
            ))
        self.assertTrue(result, 'Unexpected result of validation')

    @mock.patch('socket.socket')
    def test_tcp_ping_(self, sock):
        s = mock.Mock()
        settimeout = mock.Mock()
        connect = mock.Mock()
        close = mock.Mock()
        s.configure_mock(
            settimeout=settimeout, connect=connect, close=close)
        sock.return_value = s

        host = '127.0.0.1'
        port = 65535
        timeout = 1

        helpers.tcp_ping_(host, port)
        sock.assert_called_once()
        settimeout.assert_not_called()
        connect.assert_called_once_with((str(host), int(port)))
        close.assert_called_once()

        sock.reset_mock()
        s.reset_mock()
        settimeout.reset_mock()
        close.reset_mock()
        connect.reset_mock()

        helpers.tcp_ping_(host, port, timeout)
        sock.assert_called_once()
        settimeout.assert_called_once_with(timeout)
        connect.assert_called_once_with((str(host), int(port)))
        close.assert_called_once()

    @mock.patch('devops.helpers.helpers.tcp_ping_', autospec=True)
    def test_tcp_ping(self, ping):

        host = '127.0.0.1'
        port = 65535
        timeout = 1

        result = helpers.tcp_ping(host, port, timeout)
        ping.assert_called_once_with(host, port, timeout)
        self.assertTrue(result)

        ping.reset_mock()
        ping.side_effect = socket.error

        result = helpers.tcp_ping(host, port, timeout)
        ping.assert_called_once_with(host, port, timeout)
        self.assertFalse(result)

    @mock.patch('time.time', autospec=True)
    @mock.patch('time.sleep', autospec=True)
    def test_wait(self, sleep, time):
        time.return_value = 1
        predicate = mock.Mock(return_value=True)

        result = helpers.wait(predicate, interval=0, timeout=0)

        self.assertTrue(result)
        predicate.assert_called_once()
        time.assert_called_once()
        sleep.assert_not_called()

        time.reset_mock()
        time.return_value = 1
        sleep.reset_mock()
        predicate.reset_mock()
        predicate.return_value = True

        result = helpers.wait(predicate, interval=2, timeout=2)

        self.assertEqual(result, 2)
        predicate.assert_called_once()
        sleep.assert_not_called()
        time.assert_has_calls([mock.call(), mock.call()])

        time.reset_mock()
        time.return_value = 1
        sleep.reset_mock()
        predicate.reset_mock()
        predicate.return_value = False

        self.assertRaises(
            error.TimeoutError,
            helpers.wait,
            predicate, interval=2, timeout=-2)
        sleep.assert_not_called()
        time.assert_has_calls([mock.call(), mock.call()])

    @mock.patch('time.time', autospec=True)
    @mock.patch('time.sleep', autospec=True)
    def test_wait_pass(self, sleep, time):
        predicate = mock.Mock(return_value=True)

        result = helpers.wait_pass(predicate)
        self.assertTrue(result)
        time.assert_called_once()
        sleep.assert_not_called()

        time.reset_mock()
        time.return_value = 1
        sleep.reset_mock()
        predicate.reset_mock()
        predicate.side_effect = ValueError
        self.assertRaises(
            ValueError,
            helpers.wait_pass,
            predicate, timeout=-1)
        sleep.assert_not_called()
        time.assert_has_calls([mock.call(), mock.call()])

    @mock.patch('devops.helpers.helpers.tcp_ping', autospec=True)
    @mock.patch('time.time', autospec=True)
    @mock.patch('time.sleep', autospec=True)
    def test_wait_tcp(self, sleep, time, ping):
        host = '127.0.0.1'
        port = 65535
        timeout = 0

        helpers.wait_tcp(host, port, timeout)

        ping.assert_called_once_with(host=host, port=port)
        time.assert_called_once()
        sleep.assert_not_called()

    @mock.patch('devops.helpers.ssh_client.SSHClient', autospec=True)
    @mock.patch('devops.helpers.helpers.wait')
    def test_wait_ssh_cmd(self, wait, ssh):
        host = '127.0.0.1'
        port = 65535
        check_cmd = 'ls ~'
        username = 'user'
        password = 'pass'
        timeout = 0

        helpers.wait_ssh_cmd(
            host, port, check_cmd, username, password, timeout)
        ssh.assert_called_once_with(
            host=host, port=port,
            auth=ssh_client.SSHAuth(username=username, password=password)
        )
        wait.assert_called_once()
        # Todo: cover ssh_client.execute

    @mock.patch('six.moves.http_client.HTTPConnection', autospec=True)
    def test_http(self, connection):
        host = 'localhost'
        port = 80
        method = 'GET'
        url = '/'
        waited_code = 200

        class Res(object):
            status = waited_code

        conn = mock.Mock()
        connection.return_value = conn
        request = mock.Mock()
        getresponse = mock.Mock(return_value=Res())
        conn.configure_mock(getresponse=getresponse, request=request)

        result = helpers.http()
        self.assertTrue(result)
        connection.assert_called_once_with(host, port)
        request.assert_called_once_with(method, url)
        getresponse.assert_called_once()

        connection.reset_mock()
        request.reset_mock()
        getresponse.reset_mock()
        conn.reset_mock()
        conn.configure_mock(getresponse=getresponse, request=request)
        getresponse.return_value = Res()

        result = helpers.http(waited_code=404)
        self.assertFalse(result)
        connection.assert_called_once_with(host, port)
        request.assert_called_once_with(method, url)
        getresponse.assert_called_once()

        connection.reset_mock()
        request.reset_mock()
        getresponse.reset_mock()
        conn.reset_mock()
        conn.configure_mock(getresponse=getresponse, request=request)
        getresponse.return_value = Res()
        getresponse.side_effect = Exception

        result = helpers.http()
        self.assertFalse(result)
        connection.assert_called_once_with(host, port)
        request.assert_called_once_with(method, url)
        getresponse.assert_called_once()

    @mock.patch('six.moves.xmlrpc_client.Server', autospec=True)
    def test_xmlrpctoken(self, srv):
        server = mock.Mock()
        login = mock.Mock(return_value=True)
        server.configure_mock(login=login)
        srv.return_value = server
        uri = 'http://127.0.0.1'
        user = 'login'
        password = 'pass'

        result = helpers.xmlrpctoken(uri, user, password)
        self.assertTrue(result)
        srv.assert_called_once_with(uri)
        login.assert_called_once_with(user, password)

        srv.reset_mock()
        server.reset_mock()
        login.reset_mock()
        server.configure_mock(login=login)
        srv.return_value = server
        login.side_effect = Exception
        self.assertRaises(
            error.AuthenticationError,
            helpers.xmlrpctoken,
            uri, user, password
        )
        srv.assert_called_once_with(uri)
        login.assert_called_once_with(user, password)

    @mock.patch('six.moves.xmlrpc_client.Server', autospec=True)
    def test_xmlrpcmethod(self, srv):
        class Success(object):
            success = True

        class Fail(object):
            def __getattr__(self, item):
                raise Exception()

        uri = 'http://127.0.0.1'
        srv.side_effect = [Success(), Success(), Fail()]
        result = helpers.xmlrpcmethod(uri, 'success')
        self.assertTrue(result)
        srv.assert_called_once_with(uri)

        srv.reset_mock()
        self.assertRaises(
            AttributeError,
            helpers.xmlrpcmethod,
            uri, 'failure'
        )
        srv.assert_called_once_with(uri)

        srv.reset_mock()
        self.assertRaises(
            AttributeError,
            helpers.xmlrpcmethod,
            uri, 'success'
        )
        srv.assert_called_once_with(uri)

    @mock.patch('os.urandom', autospec=True)
    def test_generate_mac(self, rand):
        rand.return_value = b'\x01\x02\x03\x04\x05'
        result = helpers.generate_mac()
        self.assertEqual(result, '64:01:02:03:04:05')
        rand.assert_called_once_with(5)

    def test_deepgetattr(self):
        # pylint: disable=attribute-defined-outside-init
        class Tst(object):
            one = 1

        tst = Tst()
        tst2 = Tst()
        tst2.two = Tst()
        # pylint: enable=attribute-defined-outside-init

        result = helpers.deepgetattr(tst, 'one')
        self.assertEqual(result, 1)
        result = helpers.deepgetattr(tst2, 'two.one')
        self.assertEqual(result, 1)
        result = helpers.deepgetattr(tst, 'two.one')
        self.assertIsNone(result)
        result = helpers.deepgetattr(tst, 'two.one', default=0)
        self.assertEqual(result, 0)
        result = helpers.deepgetattr(tst2, 'two_one', splitter='_')
        self.assertEqual(result, 1)
        self.assertRaises(
            AttributeError,
            helpers.deepgetattr,
            tst, 'two.one', do_raise=True
        )

    def test_underscored(self):
        result = helpers.underscored('single')
        self.assertEqual(result, 'single')
        result = helpers.underscored('m', 'u', 'l', 't', 'i', 'p', 'l', 'e')
        self.assertEqual(result, 'm_u_l_t_i_p_l_e')
