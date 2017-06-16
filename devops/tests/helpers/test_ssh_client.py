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

from __future__ import unicode_literals

# pylint: disable=no-self-use

import base64
import contextlib
from os import path
import posixpath
import stat
import unittest

import mock
import paramiko
# noinspection PyUnresolvedReferences
from six.moves import cStringIO

from devops import error
from devops.helpers import exec_result
from devops.helpers import ssh_client


def gen_private_keys(amount=1):
    keys = []
    for _ in range(amount):
        keys.append(paramiko.RSAKey.generate(1024))
    return keys


def gen_public_key(private_key=None):
    if private_key is None:
        private_key = paramiko.RSAKey.generate(1024)
    return '{0} {1}'.format(private_key.get_name(), private_key.get_base64())


class FakeStream(object):
    def __init__(self, *args):
        self.__src = list(args)

    def __iter__(self):
        if len(self.__src) == 0:
            raise IOError()
        for _ in range(len(self.__src)):
            yield self.__src.pop(0)


host = '127.0.0.1'
port = 22
username = 'user'
password = 'pass'
private_keys = []
command = 'ls ~\nline 2\nline 3'
command_log = '''Executing command: \'ls ~
line 2
line 3\''''
stdout_list = [b' \n', b'2\n', b'3\n', b' \n']
stderr_list = [b' \n', b'0\n', b'1\n', b' \n']
encoded_cmd = base64.b64encode(
    "{}\n".format(command).encode('utf-8')
).decode('utf-8')


# noinspection PyTypeChecker
class TestSSHAuth(unittest.TestCase):
    def tearDown(self):
        ssh_client.SSHClient._clear_cache()

    def init_checks(self, username=None, password=None, key=None, keys=None):
        """shared positive init checks

        :type username: str
        :type password: str
        :type key: paramiko.RSAKey
        :type keys: list
        """
        auth = ssh_client.SSHAuth(
            username=username,
            password=password,
            key=key,
            keys=keys
        )

        int_keys = [None]
        if key is not None:
            int_keys.append(key)
        if keys is not None:
            for k in keys:
                if k not in int_keys:
                    int_keys.append(k)

        self.assertEqual(auth.username, username)
        with contextlib.closing(cStringIO()) as tgt:
            auth.enter_password(tgt)
            self.assertEqual(tgt.getvalue(), '{}\n'.format(password))
        self.assertEqual(
            auth.public_key,
            gen_public_key(key) if key is not None else None)

        _key = (
            None if auth.public_key is None else
            '<private for pub: {}>'.format(auth.public_key)
        )
        _keys = []
        for k in int_keys:
            if k == key:
                continue
            _keys.append(
                '<private for pub: {}>'.format(
                    gen_public_key(k)) if k is not None else None)

        self.assertEqual(
            repr(auth),
            "{cls}("
            "username={username}, "
            "password=<*masked*>, "
            "key={key}, "
            "keys={keys})".format(
                cls=ssh_client.SSHAuth.__name__,
                username=auth.username,
                key=_key,
                keys=_keys
            )
        )
        self.assertEqual(
            str(auth),
            '{cls} for {username}'.format(
                cls=ssh_client.SSHAuth.__name__,
                username=auth.username,
            )
        )

    def test_init_username_only(self):
        self.init_checks(
            username=username
        )

    def test_init_username_password(self):
        self.init_checks(
            username=username,
            password=password
        )

    def test_init_username_key(self):
        self.init_checks(
            username=username,
            key=gen_private_keys(1).pop()
        )

    def test_init_username_password_key(self):
        self.init_checks(
            username=username,
            password=password,
            key=gen_private_keys(1).pop()
        )

    def test_init_username_password_keys(self):
        self.init_checks(
            username=username,
            password=password,
            keys=gen_private_keys(2)
        )

    def test_init_username_password_key_keys(self):
        self.init_checks(
            username=username,
            password=password,
            key=gen_private_keys(1).pop(),
            keys=gen_private_keys(2)
        )


# noinspection PyTypeChecker
@mock.patch('devops.helpers.ssh_client.logger', autospec=True)
@mock.patch(
    'paramiko.AutoAddPolicy', autospec=True, return_value='AutoAddPolicy')
@mock.patch('paramiko.SSHClient', autospec=True)
class TestSSHClientInit(unittest.TestCase):
    def tearDown(self):
        ssh_client.SSHClient._clear_cache()

    def init_checks(
            self,
            client, policy, logger,
            host=None, port=22,
            username=None, password=None, private_keys=None,
            auth=None
    ):
        """shared checks for positive cases

        :type client: mock.Mock
        :type policy: mock.Mock
        :type logger: mock.Mock
        :type host: str
        :type port: int
        :type username: str
        :type password: str
        :type private_keys: list
        :type auth: ssh_client.SSHAuth
        """
        _ssh = mock.call()

        ssh = ssh_client.SSHClient(
            host=host,
            port=port,
            username=username,
            password=password,
            private_keys=private_keys,
            auth=auth
        )
        client.assert_called_once()
        policy.assert_called_once()

        if auth is None:
            if private_keys is None or len(private_keys) == 0:
                logger.assert_has_calls((
                    mock.call.debug(
                        'SSHClient('
                        'host={host}, port={port}, username={username}): '
                        'initialization by username/password/private_keys '
                        'is deprecated in favor of SSHAuth usage. '
                        'Please update your code'.format(
                            host=host, port=port, username=username
                        )),
                    mock.call.info(
                        '{0}:{1}> SSHAuth was made from old style creds: '
                        'SSHAuth for {2}'.format(host, port, username))
                ))
            else:
                logger.assert_has_calls((
                    mock.call.debug(
                        'SSHClient('
                        'host={host}, port={port}, username={username}): '
                        'initialization by username/password/private_keys '
                        'is deprecated in favor of SSHAuth usage. '
                        'Please update your code'.format(
                            host=host, port=port, username=username
                        )),
                    mock.call.debug(
                        'Main key has been updated, public key is: \n'
                        '{}'.format(ssh.auth.public_key)),
                    mock.call.info(
                        '{0}:{1}> SSHAuth was made from old style creds: '
                        'SSHAuth for {2}'.format(host, port, username))
                ))
        else:
            logger.assert_not_called()

        if auth is None:
            if private_keys is None or len(private_keys) == 0:
                pkey = None
                expected_calls = [
                    _ssh,
                    _ssh.set_missing_host_key_policy('AutoAddPolicy'),
                    _ssh.connect(
                        hostname=host, password=password,
                        pkey=pkey,
                        port=port, username=username),
                ]
            else:
                pkey = private_keys[0]
                expected_calls = [
                    _ssh,
                    _ssh.set_missing_host_key_policy('AutoAddPolicy'),
                    _ssh.connect(
                        hostname=host, password=password,
                        pkey=None,
                        port=port, username=username),
                    _ssh.connect(
                        hostname=host, password=password,
                        pkey=pkey,
                        port=port, username=username),
                ]

            self.assertIn(expected_calls, client.mock_calls)

            self.assertEqual(
                ssh.auth,
                ssh_client.SSHAuth(
                    username=username,
                    password=password,
                    keys=private_keys
                )
            )
        else:
            self.assertEqual(ssh.auth, auth)

        sftp = ssh._sftp
        self.assertEqual(sftp, client().open_sftp())

        self.assertEqual(ssh._ssh, client())

        self.assertEqual(ssh.hostname, host)
        self.assertEqual(ssh.port, port)

        self.assertEqual(
            repr(ssh),
            '{cls}(host={host}, port={port}, auth={auth!r})'.format(
                cls=ssh.__class__.__name__, host=ssh.hostname,
                port=ssh.port,
                auth=ssh.auth
            )
        )

    def test_init_host(self, client, policy, logger):
        """Test with host only set"""
        self.init_checks(
            client, policy, logger,
            host=host)

    def test_init_alternate_port(self, client, policy, logger):
        """Test with alternate port"""
        self.init_checks(
            client, policy, logger,
            host=host,
            port=2222
        )

    def test_init_username(self, client, policy, logger):
        """Test with username only set from creds"""
        self.init_checks(
            client, policy, logger,
            host=host,
            username=username
        )

    def test_init_username_password(self, client, policy, logger):
        """Test with username and password set from creds"""
        self.init_checks(
            client, policy, logger,
            host=host,
            username=username,
            password=password
            )

    def test_init_username_password_empty_keys(self, client, policy, logger):
        """Test with username, password and empty keys set from creds"""
        self.init_checks(
            client, policy, logger,
            host=host,
            username=username,
            password=password,
            private_keys=[]
        )

    def test_init_username_single_key(self, client, policy, logger):
        """Test with username and single key set from creds"""
        connect = mock.Mock(
            side_effect=[
                paramiko.AuthenticationException, mock.Mock()
            ])
        _ssh = mock.Mock()
        _ssh.attach_mock(connect, 'connect')
        client.return_value = _ssh

        self.init_checks(
            client, policy, logger,
            host=host,
            username=username,
            private_keys=gen_private_keys(1)
            )

    def test_init_username_password_single_key(self, client, policy, logger):
        """Test with username, password and single key set from creds"""
        connect = mock.Mock(
            side_effect=[
                paramiko.AuthenticationException, mock.Mock()
            ])
        _ssh = mock.Mock()
        _ssh.attach_mock(connect, 'connect')
        client.return_value = _ssh

        self.init_checks(
            client, policy, logger,
            host=host,
            username=username,
            password=password,
            private_keys=gen_private_keys(1)
        )

    def test_init_username_multiple_keys(self, client, policy, logger):
        """Test with username and multiple keys set from creds"""
        connect = mock.Mock(
            side_effect=[
                paramiko.AuthenticationException, mock.Mock()
            ])
        _ssh = mock.Mock()
        _ssh.attach_mock(connect, 'connect')
        client.return_value = _ssh

        self.init_checks(
            client, policy, logger,
            host=host,
            username=username,
            private_keys=gen_private_keys(2)
        )

    def test_init_username_password_multiple_keys(
            self, client, policy, logger):
        """Test with username, password and multiple keys set from creds"""
        connect = mock.Mock(
            side_effect=[
                paramiko.AuthenticationException, mock.Mock()
            ])
        _ssh = mock.Mock()
        _ssh.attach_mock(connect, 'connect')
        client.return_value = _ssh

        connect = mock.Mock(
            side_effect=[
                paramiko.AuthenticationException, mock.Mock()
            ])
        _ssh = mock.Mock()
        _ssh.attach_mock(connect, 'connect')
        client.return_value = _ssh

        self.init_checks(
            client, policy, logger,
            host=host,
            username=username,
            password=password,
            private_keys=gen_private_keys(2)
        )

    def test_init_auth(self, client, policy, logger):
        self.init_checks(
            client, policy, logger,
            host=host,
            auth=ssh_client.SSHAuth(
                username=username,
                password=password,
                key=gen_private_keys(1).pop()
            )
        )

    def test_init_auth_break(self, client, policy, logger):
        self.init_checks(
            client, policy, logger,
            host=host,
            username='Invalid',
            password='Invalid',
            private_keys=gen_private_keys(1),
            auth=ssh_client.SSHAuth(
                username=username,
                password=password,
                key=gen_private_keys(1).pop()
            )
        )

    def test_init_context(self, client, policy, logger):
        with ssh_client.SSHClient(host=host, auth=ssh_client.SSHAuth()) as ssh:
            client.assert_called_once()
            policy.assert_called_once()

            logger.assert_not_called()

            self.assertEqual(ssh.auth, ssh_client.SSHAuth())

            sftp = ssh._sftp
            self.assertEqual(sftp, client().open_sftp())

            self.assertEqual(ssh._ssh, client())

            self.assertEqual(ssh.hostname, host)
            self.assertEqual(ssh.port, port)

    def test_init_clear_failed(self, client, policy, logger):
        """Test reconnect

        :type client: mock.Mock
        :type policy: mock.Mock
        :type logger: mock.Mock
        """
        _ssh = mock.Mock()
        _ssh.attach_mock(
            mock.Mock(
                side_effect=[
                    Exception('Mocked SSH close()'),
                    mock.Mock()
                ]),
            'close')
        _sftp = mock.Mock()
        _sftp.attach_mock(
            mock.Mock(
                side_effect=[
                    Exception('Mocked SFTP close()'),
                    mock.Mock()
                ]),
            'close')
        client.return_value = _ssh
        _ssh.attach_mock(mock.Mock(return_value=_sftp), 'open_sftp')

        ssh = ssh_client.SSHClient(host=host, auth=ssh_client.SSHAuth())
        client.assert_called_once()
        policy.assert_called_once()

        logger.assert_not_called()

        self.assertEqual(ssh.auth, ssh_client.SSHAuth())

        sftp = ssh._sftp
        self.assertEqual(sftp, _sftp)

        self.assertEqual(ssh._ssh, _ssh)

        self.assertEqual(ssh.hostname, host)
        self.assertEqual(ssh.port, port)

        logger.reset_mock()

        ssh.close()

        logger.assert_has_calls((
            mock.call.exception('Could not close ssh connection'),
            mock.call.exception('Could not close sftp connection'),
        ))

    def test_init_reconnect(self, client, policy, logger):
        """Test reconnect

        :type client: mock.Mock
        :type policy: mock.Mock
        :type logger: mock.Mock
        """
        ssh = ssh_client.SSHClient(host=host, auth=ssh_client.SSHAuth())
        client.assert_called_once()
        policy.assert_called_once()

        logger.assert_not_called()

        self.assertEqual(ssh.auth, ssh_client.SSHAuth())

        sftp = ssh._sftp
        self.assertEqual(sftp, client().open_sftp())

        self.assertEqual(ssh._ssh, client())

        client.reset_mock()
        policy.reset_mock()

        self.assertEqual(ssh.hostname, host)
        self.assertEqual(ssh.port, port)

        ssh.reconnect()

        _ssh = mock.call()

        expected_calls = [
            _ssh.close(),
            _ssh,
            _ssh.set_missing_host_key_policy('AutoAddPolicy'),
            _ssh.connect(
                hostname='127.0.0.1',
                password=None,
                pkey=None,
                port=22,
                username=None),
        ]
        self.assertIn(
            expected_calls,
            client.mock_calls
        )

        client.assert_called_once()
        policy.assert_called_once()

        logger.assert_not_called()

        self.assertEqual(ssh.auth, ssh_client.SSHAuth())

        sftp = ssh._sftp
        self.assertEqual(sftp, client().open_sftp())

        self.assertEqual(ssh._ssh, client())

    @mock.patch('time.sleep', autospec=True)
    def test_init_password_required(self, sleep, client, policy, logger):
        connect = mock.Mock(side_effect=paramiko.PasswordRequiredException)
        _ssh = mock.Mock()
        _ssh.attach_mock(connect, 'connect')
        client.return_value = _ssh

        with self.assertRaises(paramiko.PasswordRequiredException):
            ssh_client.SSHClient(host=host, auth=ssh_client.SSHAuth())
        logger.assert_has_calls((
            mock.call.exception('No password has been set!'),
        ))

    @mock.patch('time.sleep', autospec=True)
    def test_init_password_broken(self, sleep, client, policy, logger):
        connect = mock.Mock(side_effect=paramiko.PasswordRequiredException)
        _ssh = mock.Mock()
        _ssh.attach_mock(connect, 'connect')
        client.return_value = _ssh

        with self.assertRaises(paramiko.PasswordRequiredException):
            ssh_client.SSHClient(
                host=host, auth=ssh_client.SSHAuth(password=password))

        logger.assert_has_calls((
            mock.call.critical(
                'Unexpected PasswordRequiredException, '
                'when password is set!'
            ),
        ))

    @mock.patch('time.sleep', autospec=True)
    def test_init_auth_impossible_password(
            self, sleep, client, policy, logger):
        connect = mock.Mock(side_effect=paramiko.AuthenticationException)

        _ssh = mock.Mock()
        _ssh.attach_mock(connect, 'connect')
        client.return_value = _ssh

        with self.assertRaises(paramiko.AuthenticationException):
            ssh_client.SSHClient(
                host=host, auth=ssh_client.SSHAuth(password=password))

        logger.assert_has_calls(
            (
                mock.call.exception(
                    'Connection using stored authentication info failed!'),
            ) * 3
        )

    @mock.patch('time.sleep', autospec=True)
    def test_init_auth_impossible_key(self, sleep, client, policy, logger):
        connect = mock.Mock(side_effect=paramiko.AuthenticationException)

        _ssh = mock.Mock()
        _ssh.attach_mock(connect, 'connect')
        client.return_value = _ssh

        with self.assertRaises(paramiko.AuthenticationException):
            ssh_client.SSHClient(
                host=host,
                auth=ssh_client.SSHAuth(key=gen_private_keys(1).pop())
            )

        logger.assert_has_calls(
            (
                mock.call.exception(
                    'Connection using stored authentication info failed!'),
            ) * 3
        )

    def test_init_auth_pass_no_key(self, client, policy, logger):
        connect = mock.Mock(
            side_effect=[
                paramiko.AuthenticationException,
                mock.Mock()
            ])

        _ssh = mock.Mock()
        _ssh.attach_mock(connect, 'connect')
        client.return_value = _ssh
        key = gen_private_keys(1).pop()

        ssh = ssh_client.SSHClient(
            host=host,
            auth=ssh_client.SSHAuth(
                username=username,
                password=password,
                key=key
            )
        )

        client.assert_called_once()
        policy.assert_called_once()

        logger.assert_has_calls((
            mock.call.debug(
                'Main key has been updated, public key is: \nNone'),
        ))

        self.assertEqual(
            ssh.auth,
            ssh_client.SSHAuth(
                username=username,
                password=password,
                keys=[key]
            )
        )

        sftp = ssh._sftp
        self.assertEqual(sftp, client().open_sftp())

        self.assertEqual(ssh._ssh, client())

    @mock.patch('time.sleep', autospec=True)
    def test_init_auth_brute_impossible(self, sleep, client, policy, logger):
        connect = mock.Mock(side_effect=paramiko.AuthenticationException)

        _ssh = mock.Mock()
        _ssh.attach_mock(connect, 'connect')
        client.return_value = _ssh

        with self.assertRaises(paramiko.AuthenticationException):
            ssh_client.SSHClient(
                host=host,
                username=username,
                private_keys=gen_private_keys(2))

        logger.assert_has_calls(
            (
                mock.call.debug(
                    'SSHClient('
                    'host={host}, port={port}, username={username}): '
                    'initialization by username/password/private_keys '
                    'is deprecated in favor of SSHAuth usage. '
                    'Please update your code'.format(
                        host=host, port=port, username=username
                    )),
            ) + (
                mock.call.exception(
                    'Connection using stored authentication info failed!'),
            ) * 3
        )

    def test_init_no_sftp(self, client, policy, logger):
        open_sftp = mock.Mock(side_effect=paramiko.SSHException)

        _ssh = mock.Mock()
        _ssh.attach_mock(open_sftp, 'open_sftp')
        client.return_value = _ssh

        ssh = ssh_client.SSHClient(
            host=host, auth=ssh_client.SSHAuth(password=password))

        with self.assertRaises(paramiko.SSHException):
            # pylint: disable=pointless-statement
            # noinspection PyStatementEffect
            ssh._sftp
            # pylint: enable=pointless-statement
        logger.assert_has_calls((
            mock.call.debug('SFTP is not connected, try to connect...'),
            mock.call.warning(
                'SFTP enable failed! SSH only is accessible.'),
        ))

    def test_init_sftp_repair(self, client, policy, logger):
        _sftp = mock.Mock()
        open_sftp = mock.Mock(
            side_effect=[
                paramiko.SSHException,
                _sftp, _sftp])

        _ssh = mock.Mock()
        _ssh.attach_mock(open_sftp, 'open_sftp')
        client.return_value = _ssh

        ssh = ssh_client.SSHClient(
            host=host, auth=ssh_client.SSHAuth(password=password))

        with self.assertRaises(paramiko.SSHException):
            # pylint: disable=pointless-statement
            # noinspection PyStatementEffect
            ssh._sftp
            # pylint: enable=pointless-statement

        logger.reset_mock()

        sftp = ssh._sftp
        self.assertEqual(sftp, open_sftp())
        logger.assert_has_calls((
            mock.call.debug('SFTP is not connected, try to connect...'),
        ))

    @mock.patch('devops.helpers.exec_result.ExecResult', autospec=True)
    def test_init_memorize(
            self,
            Result,
            client, policy, logger):
        port1 = 2222
        host1 = '127.0.0.2'

        # 1. Normal init
        ssh01 = ssh_client.SSHClient(host=host)
        ssh02 = ssh_client.SSHClient(host=host)
        ssh11 = ssh_client.SSHClient(host=host, port=port1)
        ssh12 = ssh_client.SSHClient(host=host, port=port1)
        ssh21 = ssh_client.SSHClient(host=host1)
        ssh22 = ssh_client.SSHClient(host=host1)

        self.assertTrue(ssh01 is ssh02)
        self.assertTrue(ssh11 is ssh12)
        self.assertTrue(ssh21 is ssh22)
        self.assertFalse(ssh01 is ssh11)
        self.assertFalse(ssh01 is ssh21)
        self.assertFalse(ssh11 is ssh21)

        # 2. Close connections check
        client.reset_mock()
        ssh01.close_connections(ssh01.hostname)
        client.assert_has_calls((
            mock.call().get_transport(),
            mock.call().get_transport(),
            mock.call().close(),
            mock.call().close(),
        ))
        client.reset_mock()
        ssh01.close_connections()
        # Mock returns false-connected state, so we just count close calls

        client.assert_has_calls((
            mock.call().get_transport(),
            mock.call().get_transport(),
            mock.call().get_transport(),
            mock.call().close(),
            mock.call().close(),
            mock.call().close(),
        ))

        # change creds
        ssh_client.SSHClient(
            host=host, auth=ssh_client.SSHAuth(username=username))

        # Change back: new connection differs from old with the same creds
        ssh004 = ssh_client.SSHAuth(host)
        self.assertFalse(ssh01 is ssh004)

    @mock.patch('warnings.warn')
    def test_init_memorize_close_unused(self, warn, client, policy, logger):
        ssh0 = ssh_client.SSHClient(host=host)
        text = str(ssh0)
        del ssh0  # remove reference - now it's cached and unused
        client.reset_mock()
        logger.reset_mock()
        # New connection on the same host:port with different auth
        ssh1 = ssh_client.SSHClient(
            host=host, auth=ssh_client.SSHAuth(username=username))
        logger.assert_has_calls((
            mock.call.debug('Closing {} as unused'.format(text)),
        ))
        client.assert_has_calls((
            mock.call().close(),
        ))
        text = str(ssh1)
        del ssh1  # remove reference - now it's cached and unused
        client.reset_mock()
        logger.reset_mock()
        ssh_client.SSHClient._clear_cache()
        logger.assert_has_calls((
            mock.call.debug('Closing {} as unused'.format(text)),
        ))
        client.assert_has_calls((
            mock.call().close(),
        ))

    @mock.patch(
        'devops.helpers.ssh_client.SSHClient.execute')
    def test_init_memorize_reconnect(self, execute, client, policy, logger):
        execute.side_effect = paramiko.SSHException
        ssh_client.SSHClient(host=host)
        client.reset_mock()
        policy.reset_mock()
        logger.reset_mock()
        ssh_client.SSHClient(host=host)
        client.assert_called_once()
        policy.assert_called_once()

    @mock.patch('warnings.warn')
    def test_init_clear(self, warn, client, policy, logger):
        ssh01 = ssh_client.SSHClient(host=host, auth=ssh_client.SSHAuth())

        # noinspection PyDeprecation
        ssh01.clear()
        warn.assert_called_once_with(
            "clear is removed: use close() only if it mandatory: "
            "it's automatically called on revert|shutdown|suspend|destroy",
            DeprecationWarning
        )

        self.assertNotIn(
            mock.call.close(),
            client.mock_calls
        )

    @mock.patch('warnings.warn')
    def test_deprecated_host(self, warn, client, policy, logger):
        ssh01 = ssh_client.SSHClient(host=host, auth=ssh_client.SSHAuth())
        # noinspection PyDeprecation
        self.assertEqual(ssh01.host, ssh01.hostname)
        warn.assert_called_once_with(
            'host has been deprecated in favor of hostname',
            DeprecationWarning
        )


@mock.patch('devops.helpers.ssh_client.logger', autospec=True)
@mock.patch(
    'paramiko.AutoAddPolicy', autospec=True, return_value='AutoAddPolicy')
@mock.patch('paramiko.SSHClient', autospec=True)
class TestExecute(unittest.TestCase):
    def tearDown(self):
        ssh_client.SSHClient._clear_cache()

    @staticmethod
    def get_ssh():
        """SSHClient object builder for execution tests

        :rtype: ssh_client.SSHClient
        """
        # noinspection PyTypeChecker
        return ssh_client.SSHClient(
            host=host,
            port=port,
            auth=ssh_client.SSHAuth(
                username=username,
                password=password
            ))

    def test_execute_async(self, client, policy, logger):
        chan = mock.Mock()
        open_session = mock.Mock(return_value=chan)
        transport = mock.Mock()
        transport.attach_mock(open_session, 'open_session')
        get_transport = mock.Mock(return_value=transport)
        _ssh = mock.Mock()
        _ssh.attach_mock(get_transport, 'get_transport')
        client.return_value = _ssh

        ssh = self.get_ssh()

        # noinspection PyTypeChecker
        result = ssh.execute_async(command=command)
        get_transport.assert_called_once()
        open_session.assert_called_once()

        self.assertIn(chan, result)
        chan.assert_has_calls((
            mock.call.makefile('wb'),
            mock.call.makefile('rb'),
            mock.call.makefile_stderr('rb'),
            mock.call.exec_command('{}\n'.format(command))
        ))
        self.assertIn(
            mock.call.debug(command_log),
            logger.mock_calls
        )

    def test_execute_async_pty(self, client, policy, logger):
        chan = mock.Mock()
        open_session = mock.Mock(return_value=chan)
        transport = mock.Mock()
        transport.attach_mock(open_session, 'open_session')
        get_transport = mock.Mock(return_value=transport)
        _ssh = mock.Mock()
        _ssh.attach_mock(get_transport, 'get_transport')
        client.return_value = _ssh

        ssh = self.get_ssh()

        # noinspection PyTypeChecker
        result = ssh.execute_async(command=command, get_pty=True)
        get_transport.assert_called_once()
        open_session.assert_called_once()

        self.assertIn(chan, result)
        chan.assert_has_calls((
            mock.call.get_pty(
                term='vt100',
                width=80, height=24,
                width_pixels=0, height_pixels=0
            ),
            mock.call.makefile('wb'),
            mock.call.makefile('rb'),
            mock.call.makefile_stderr('rb'),
            mock.call.exec_command('{}\n'.format(command))
        ))
        self.assertIn(
            mock.call.debug(command_log),
            logger.mock_calls
        )

    def test_execute_async_sudo(self, client, policy, logger):
        chan = mock.Mock()
        open_session = mock.Mock(return_value=chan)
        transport = mock.Mock()
        transport.attach_mock(open_session, 'open_session')
        get_transport = mock.Mock(return_value=transport)
        _ssh = mock.Mock()
        _ssh.attach_mock(get_transport, 'get_transport')
        client.return_value = _ssh

        ssh = self.get_ssh()
        ssh.sudo_mode = True

        # noinspection PyTypeChecker
        result = ssh.execute_async(command=command)
        get_transport.assert_called_once()
        open_session.assert_called_once()

        self.assertIn(chan, result)
        chan.assert_has_calls((
            mock.call.makefile('wb'),
            mock.call.makefile('rb'),
            mock.call.makefile_stderr('rb'),
            mock.call.exec_command(
                "sudo -S bash -c '"
                "eval \"$(base64 -d <(echo \"{0}\"))\"'".format(encoded_cmd))
        ))
        self.assertIn(
            mock.call.debug(command_log),
            logger.mock_calls
        )

    def test_execute_async_with_sudo_enforce(self, client, policy, logger):
        chan = mock.Mock()
        open_session = mock.Mock(return_value=chan)
        transport = mock.Mock()
        transport.attach_mock(open_session, 'open_session')
        get_transport = mock.Mock(return_value=transport)
        _ssh = mock.Mock()
        _ssh.attach_mock(get_transport, 'get_transport')
        client.return_value = _ssh

        ssh = self.get_ssh()
        self.assertFalse(ssh.sudo_mode)
        with ssh_client.SSHClient.sudo(ssh, enforce=True):
            self.assertTrue(ssh.sudo_mode)
            # noinspection PyTypeChecker
            result = ssh.execute_async(command=command)
        self.assertFalse(ssh.sudo_mode)

        get_transport.assert_called_once()
        open_session.assert_called_once()

        self.assertIn(chan, result)
        chan.assert_has_calls((
            mock.call.makefile('wb'),
            mock.call.makefile('rb'),
            mock.call.makefile_stderr('rb'),
            mock.call.exec_command(
                "sudo -S bash -c '"
                "eval \"$(base64 -d <(echo \"{0}\"))\"'".format(encoded_cmd))
        ))
        self.assertIn(
            mock.call.debug(command_log),
            logger.mock_calls
        )

    def test_execute_async_with_no_sudo_enforce(self, client, policy, logger):
        chan = mock.Mock()
        open_session = mock.Mock(return_value=chan)
        transport = mock.Mock()
        transport.attach_mock(open_session, 'open_session')
        get_transport = mock.Mock(return_value=transport)
        _ssh = mock.Mock()
        _ssh.attach_mock(get_transport, 'get_transport')
        client.return_value = _ssh

        ssh = self.get_ssh()
        ssh.sudo_mode = True

        with ssh.sudo(enforce=False):
            # noinspection PyTypeChecker
            result = ssh.execute_async(command=command)
        get_transport.assert_called_once()
        open_session.assert_called_once()

        self.assertIn(chan, result)
        chan.assert_has_calls((
            mock.call.makefile('wb'),
            mock.call.makefile('rb'),
            mock.call.makefile_stderr('rb'),
            mock.call.exec_command('{}\n'.format(command))
        ))
        self.assertIn(
            mock.call.debug(command_log),
            logger.mock_calls
        )

    def test_execute_async_with_none_enforce(self, client, policy, logger):
        chan = mock.Mock()
        open_session = mock.Mock(return_value=chan)
        transport = mock.Mock()
        transport.attach_mock(open_session, 'open_session')
        get_transport = mock.Mock(return_value=transport)
        _ssh = mock.Mock()
        _ssh.attach_mock(get_transport, 'get_transport')
        client.return_value = _ssh

        ssh = self.get_ssh()
        ssh.sudo_mode = False

        with ssh.sudo():
            # noinspection PyTypeChecker
            result = ssh.execute_async(command=command)
        get_transport.assert_called_once()
        open_session.assert_called_once()

        self.assertIn(chan, result)
        chan.assert_has_calls((
            mock.call.makefile('wb'),
            mock.call.makefile('rb'),
            mock.call.makefile_stderr('rb'),
            mock.call.exec_command('{}\n'.format(command))
        ))
        self.assertIn(
            mock.call.debug(command_log),
            logger.mock_calls
        )

    @mock.patch('devops.helpers.ssh_client.SSHAuth.enter_password')
    def test_execute_async_sudo_password(
            self, enter_password, client, policy, logger):
        stdin = mock.Mock(name='stdin')
        stdout = mock.Mock(name='stdout')
        stdout_channel = mock.Mock()
        stdout_channel.configure_mock(closed=False)
        stdout.attach_mock(stdout_channel, 'channel')
        makefile = mock.Mock(side_effect=[stdin, stdout])
        chan = mock.Mock()
        chan.attach_mock(makefile, 'makefile')
        open_session = mock.Mock(return_value=chan)
        transport = mock.Mock()
        transport.attach_mock(open_session, 'open_session')
        get_transport = mock.Mock(return_value=transport)
        _ssh = mock.Mock()
        _ssh.attach_mock(get_transport, 'get_transport')
        client.return_value = _ssh

        ssh = self.get_ssh()
        ssh.sudo_mode = True

        # noinspection PyTypeChecker
        result = ssh.execute_async(command=command)
        get_transport.assert_called_once()
        open_session.assert_called_once()
        # raise ValueError(closed.mock_calls)
        enter_password.assert_called_once_with(stdin)
        stdin.assert_has_calls((mock.call.flush(), ))

        self.assertIn(chan, result)
        chan.assert_has_calls((
            mock.call.makefile('wb'),
            mock.call.makefile('rb'),
            mock.call.makefile_stderr('rb'),
            mock.call.exec_command(
                "sudo -S bash -c '"
                "eval \"$(base64 -d <(echo \"{0}\"))\"'".format(encoded_cmd))
        ))
        self.assertIn(
            mock.call.debug(command_log),
            logger.mock_calls
        )

    @staticmethod
    def get_patched_execute_async_retval(ec=0, stderr_val=None):
        """get patched execute_async retval

        :rtype:
            Tuple(
                mock.Mock,
                str,
                exec_result.ExecResult,
                FakeStream,
                FakeStream)
        """
        out = stdout_list
        err = stderr_list if stderr_val is None else []

        stdout = FakeStream(*out)
        stderr = FakeStream(*err)

        exit_code = ec
        chan = mock.Mock()
        recv_exit_status = mock.Mock(return_value=exit_code)
        chan.attach_mock(recv_exit_status, 'recv_exit_status')

        wait = mock.Mock()
        status_event = mock.Mock()
        status_event.attach_mock(wait, 'wait')
        chan.attach_mock(status_event, 'status_event')
        chan.configure_mock(exit_status=exit_code)

        # noinspection PyTypeChecker
        exp_result = exec_result.ExecResult(
            cmd=command,
            stderr=err,
            stdout=out,
            exit_code=ec
        )

        return chan, '', exp_result, stderr, stdout

    @mock.patch(
        'devops.helpers.ssh_client.SSHClient.execute_async')
    def test_execute(
            self,
            execute_async,
            client, policy, logger):
        (
            chan, _stdin, exp_result, stderr, stdout
        ) = self.get_patched_execute_async_retval()
        is_set = mock.Mock(return_value=True)
        chan.status_event.attach_mock(is_set, 'is_set')

        execute_async.return_value = chan, _stdin, stderr, stdout

        ssh = self.get_ssh()

        logger.reset_mock()

        # noinspection PyTypeChecker
        result = ssh.execute(command=command, verbose=False)

        self.assertEqual(
            result,
            exp_result
        )
        execute_async.assert_called_once_with(command)
        chan.assert_has_calls((mock.call.status_event.is_set(), ))
        logger.assert_has_calls([
            mock.call.debug(command_log),
            ] + [
                mock.call.debug(str(x.rstrip().decode('utf-8')))
                for x in stdout_list
            ] + [
                mock.call.debug(str(x.rstrip().decode('utf-8')))
                for x in stderr_list
            ] + [
            mock.call.debug(
                '\n{cmd!r} execution results: '
                'Exit code: {code!s}'.format(
                    cmd=command,
                    code=result.exit_code,
                )),
        ])

    @mock.patch(
        'devops.helpers.ssh_client.SSHClient.execute_async')
    def test_execute_verbose(
            self,
            execute_async,
            client, policy, logger):
        (
            chan, _stdin, exp_result, stderr, stdout
        ) = self.get_patched_execute_async_retval()
        is_set = mock.Mock(return_value=True)
        chan.status_event.attach_mock(is_set, 'is_set')

        execute_async.return_value = chan, _stdin, stderr, stdout

        ssh = self.get_ssh()

        logger.reset_mock()

        # noinspection PyTypeChecker
        result = ssh.execute(command=command, verbose=True)

        self.assertEqual(
            result,
            exp_result
        )
        execute_async.assert_called_once_with(command)
        chan.assert_has_calls((mock.call.status_event.is_set(), ))

        logger.assert_has_calls([
            mock.call.info(command_log),
            ] + [
                mock.call.info(str(x.rstrip().decode('utf-8')))
                for x in stdout_list
            ] + [
                mock.call.error(str(x.rstrip().decode('utf-8')))
                for x in stderr_list
            ] + [
            mock.call.info(
                '\n{cmd!r} execution results: '
                'Exit code: {code!s}'.format(
                    cmd=command,
                    code=result.exit_code,
                )),
        ])

    @mock.patch('time.sleep', autospec=True)
    @mock.patch(
        'devops.helpers.ssh_client.SSHClient.execute_async')
    def test_execute_timeout(
            self,
            execute_async, sleep,
            client, policy, logger):
        (
            chan, _stdin, exp_result, stderr, stdout
        ) = self.get_patched_execute_async_retval()
        is_set = mock.Mock(return_value=True)
        chan.status_event.attach_mock(is_set, 'is_set')

        execute_async.return_value = chan, _stdin, stderr, stdout

        ssh = self.get_ssh()

        logger.reset_mock()

        # noinspection PyTypeChecker
        result = ssh.execute(command=command, verbose=False, timeout=1)

        self.assertEqual(
            result,
            exp_result
        )
        execute_async.assert_called_once_with(command)
        chan.assert_has_calls((mock.call.status_event.is_set(), ))
        logger.assert_has_calls((
            mock.call.debug(
                '\n{cmd!r} execution results: '
                'Exit code: {code!s}'.format(
                    cmd=exp_result.cmd,
                    code=exp_result.exit_code
                )),
        ))

    @mock.patch(
        'devops.helpers.ssh_client.SSHClient.execute_async')
    def test_execute_timeout_fail(
            self,
            execute_async,
            client, policy, logger):
        (
            chan, _stdin, _, stderr, stdout
        ) = self.get_patched_execute_async_retval()
        is_set = mock.Mock(return_value=False)
        chan.status_event.attach_mock(is_set, 'is_set')
        chan.status_event.attach_mock(mock.Mock(), 'wait')

        execute_async.return_value = chan, _stdin, stderr, stdout

        ssh = self.get_ssh()

        logger.reset_mock()

        with self.assertRaises(error.TimeoutError):
            # noinspection PyTypeChecker
            ssh.execute(command=command, verbose=False, timeout=1)

        execute_async.assert_called_once_with(command)
        chan.assert_has_calls((mock.call.status_event.is_set(), ))

    @mock.patch(
        'devops.helpers.ssh_client.SSHClient.execute_async')
    def test_execute_together(self, execute_async, client, policy, logger):
        (
            chan, _stdin, _, stderr, stdout
        ) = self.get_patched_execute_async_retval()
        execute_async.return_value = chan, _stdin, stderr, stdout

        host2 = '127.0.0.2'

        ssh = self.get_ssh()
        # noinspection PyTypeChecker
        ssh2 = ssh_client.SSHClient(
            host=host2,
            port=port,
            auth=ssh_client.SSHAuth(
                username=username,
                password=password
            ))

        remotes = [ssh, ssh2]

        # noinspection PyTypeChecker
        ssh_client.SSHClient.execute_together(
            remotes=remotes, command=command)

        self.assertEqual(execute_async.call_count, len(remotes))
        chan.assert_has_calls((
            mock.call.recv_exit_status(),
            mock.call.close(),
            mock.call.recv_exit_status(),
            mock.call.close()
        ))

        # noinspection PyTypeChecker
        ssh_client.SSHClient.execute_together(
            remotes=remotes, command=command, expected=[1], raise_on_err=False)

        with self.assertRaises(error.DevopsCalledProcessError):
            # noinspection PyTypeChecker
            ssh_client.SSHClient.execute_together(
                remotes=remotes, command=command, expected=[1])

    @mock.patch(
        'devops.helpers.ssh_client.SSHClient.execute')
    def test_check_call(self, execute, client, policy, logger):
        exit_code = 0
        return_value = {
            'stderr_str': '0\n1',
            'stdout_str': '2\n3',
            'stderr_brief': '0\n1',
            'stdout_brief': '2\n3',
            'exit_code': exit_code,
            'stderr': [b' \n', b'0\n', b'1\n', b' \n'],
            'stdout': [b' \n', b'2\n', b'3\n', b' \n']}
        execute.return_value = return_value

        verbose = False

        ssh = self.get_ssh()

        # noinspection PyTypeChecker
        result = ssh.check_call(command=command, verbose=verbose, timeout=None)
        execute.assert_called_once_with(command, verbose, None)
        self.assertEqual(result, return_value)

        exit_code = 1
        return_value['exit_code'] = exit_code
        execute.reset_mock()
        execute.return_value = return_value
        with self.assertRaises(error.DevopsCalledProcessError):
            # noinspection PyTypeChecker
            ssh.check_call(command=command, verbose=verbose, timeout=None)
        execute.assert_called_once_with(command, verbose, None)

    @mock.patch(
        'devops.helpers.ssh_client.SSHClient.execute')
    def test_check_call_expected(self, execute, client, policy, logger):
        exit_code = 0
        return_value = {
            'stderr_str': '0\n1',
            'stdout_str': '2\n3',
            'stderr_brief': '0\n1',
            'stdout_brief': '2\n3',
            'exit_code': exit_code,
            'stderr': [b' \n', b'0\n', b'1\n', b' \n'],
            'stdout': [b' \n', b'2\n', b'3\n', b' \n']}
        execute.return_value = return_value

        verbose = False

        ssh = self.get_ssh()

        # noinspection PyTypeChecker
        result = ssh.check_call(
            command=command, verbose=verbose, timeout=None, expected=[0, 75])
        execute.assert_called_once_with(command, verbose, None)
        self.assertEqual(result, return_value)

        exit_code = 1
        return_value['exit_code'] = exit_code
        execute.reset_mock()
        execute.return_value = return_value
        with self.assertRaises(error.DevopsCalledProcessError):
            # noinspection PyTypeChecker
            ssh.check_call(
                command=command, verbose=verbose, timeout=None,
                expected=[0, 75]
            )
        execute.assert_called_once_with(command, verbose, None)

    @mock.patch(
        'devops.helpers.ssh_client.SSHClient.check_call')
    def test_check_stderr(self, check_call, client, policy, logger):
        return_value = {
            'stderr_str': '',
            'stdout_str': '2\n3',
            'stderr_brief': '',
            'stdout_brief': '2\n3',
            'exit_code': 0,
            'stderr': [],
            'stdout': [b' \n', b'2\n', b'3\n', b' \n']}
        check_call.return_value = return_value

        verbose = False
        raise_on_err = True

        ssh = self.get_ssh()

        # noinspection PyTypeChecker
        result = ssh.check_stderr(
            command=command, verbose=verbose, timeout=None,
            raise_on_err=raise_on_err)
        check_call.assert_called_once_with(
            command, verbose, timeout=None,
            error_info=None, raise_on_err=raise_on_err)
        self.assertEqual(result, return_value)

        return_value['stderr_str'] = '0\n1'
        return_value['stderr'] = [b' \n', b'0\n', b'1\n', b' \n']

        check_call.reset_mock()
        check_call.return_value = return_value
        with self.assertRaises(error.DevopsCalledProcessError):
            # noinspection PyTypeChecker
            ssh.check_stderr(
                command=command, verbose=verbose, timeout=None,
                raise_on_err=raise_on_err)
        check_call.assert_called_once_with(
            command, verbose, timeout=None,
            error_info=None, raise_on_err=raise_on_err)


@mock.patch('devops.helpers.ssh_client.logger', autospec=True)
@mock.patch(
    'paramiko.AutoAddPolicy', autospec=True, return_value='AutoAddPolicy')
@mock.patch('paramiko.SSHClient', autospec=True)
@mock.patch('paramiko.Transport', autospec=True)
class TestExecuteThrowHost(unittest.TestCase):
    def tearDown(self):
        ssh_client.SSHClient._clear_cache()

    @staticmethod
    def prepare_execute_through_host(transp, client, exit_code):
        intermediate_channel = mock.Mock(name='intermediate_channel')

        open_channel = mock.Mock(
            return_value=intermediate_channel,
            name='open_channel'
        )
        intermediate_transport = mock.Mock(name='intermediate_transport')
        intermediate_transport.attach_mock(open_channel, 'open_channel')
        get_transport = mock.Mock(
            return_value=intermediate_transport,
            name='get_transport'
        )

        _ssh = mock.Mock(neme='_ssh')
        _ssh.attach_mock(get_transport, 'get_transport')
        client.return_value = _ssh

        transport = mock.Mock(name='transport')
        transp.return_value = transport

        recv_exit_status = mock.Mock(return_value=exit_code)

        channel = mock.Mock()
        channel.attach_mock(
            mock.Mock(return_value=FakeStream(b' \n', b'2\n', b'3\n', b' \n')),
            'makefile')
        channel.attach_mock(
            mock.Mock(return_value=FakeStream(b' \n', b'0\n', b'1\n', b' \n')),
            'makefile_stderr')

        channel.attach_mock(recv_exit_status, 'recv_exit_status')
        open_session = mock.Mock(return_value=channel, name='open_session')
        transport.attach_mock(open_session, 'open_session')

        wait = mock.Mock()
        status_event = mock.Mock()
        status_event.attach_mock(wait, 'wait')
        channel.attach_mock(status_event, 'status_event')
        channel.configure_mock(exit_status=exit_code)

        is_set = mock.Mock(return_value=True)
        channel.status_event.attach_mock(is_set, 'is_set')

        return (
            open_session, transport, channel, get_transport,
            open_channel, intermediate_channel
        )

    def test_execute_through_host_no_creds(
            self, transp, client, policy, logger):
        target = '127.0.0.2'
        exit_code = 0

        # noinspection PyTypeChecker
        return_value = exec_result.ExecResult(
            cmd=command,
            stderr=[b' \n', b'0\n', b'1\n', b' \n'],
            stdout=[b' \n', b'2\n', b'3\n', b' \n'],
            exit_code=exit_code
        )

        (
            open_session,
            transport,
            channel,
            get_transport,
            open_channel,
            intermediate_channel
        ) = self.prepare_execute_through_host(
            transp=transp,
            client=client,
            exit_code=exit_code)

        # noinspection PyTypeChecker
        ssh = ssh_client.SSHClient(
            host=host,
            port=port,
            auth=ssh_client.SSHAuth(
                username=username,
                password=password
            ))

        # noinspection PyTypeChecker
        result = ssh.execute_through_host(target, command)
        self.assertEqual(result, return_value)
        get_transport.assert_called_once()
        open_channel.assert_called_once()
        transp.assert_called_once_with(intermediate_channel)
        open_session.assert_called_once()
        transport.assert_has_calls((
            mock.call.connect(username=username, password=password, pkey=None),
            mock.call.open_session()
        ))
        channel.assert_has_calls((
            mock.call.makefile('rb'),
            mock.call.makefile_stderr('rb'),
            mock.call.exec_command(command),
            mock.call.recv_ready(),
            mock.call.recv_stderr_ready(),
            mock.call.status_event.is_set(),
            mock.call.close()
        ))

    def test_execute_through_host_auth(
            self, transp, client, policy, logger):
        _login = 'cirros'
        _password = 'cubswin:)'

        target = '127.0.0.2'
        exit_code = 0

        # noinspection PyTypeChecker
        return_value = exec_result.ExecResult(
            cmd=command,
            stderr=[b' \n', b'0\n', b'1\n', b' \n'],
            stdout=[b' \n', b'2\n', b'3\n', b' \n'],
            exit_code=exit_code
        )

        (
            open_session, transport, channel, get_transport,
            open_channel, intermediate_channel
        ) = self.prepare_execute_through_host(
            transp, client, exit_code=exit_code)

        # noinspection PyTypeChecker
        ssh = ssh_client.SSHClient(
            host=host,
            port=port,
            auth=ssh_client.SSHAuth(
                username=username,
                password=password
            ))

        # noinspection PyTypeChecker
        result = ssh.execute_through_host(
            target, command,
            auth=ssh_client.SSHAuth(username=_login, password=_password))
        self.assertEqual(result, return_value)
        get_transport.assert_called_once()
        open_channel.assert_called_once()
        transp.assert_called_once_with(intermediate_channel)
        open_session.assert_called_once()
        transport.assert_has_calls((
            mock.call.connect(username=_login, password=_password, pkey=None),
            mock.call.open_session()
        ))
        channel.assert_has_calls((
            mock.call.makefile('rb'),
            mock.call.makefile_stderr('rb'),
            mock.call.exec_command(command),
            mock.call.recv_ready(),
            mock.call.recv_stderr_ready(),
            mock.call.status_event.is_set(),
            mock.call.close()
        ))


@mock.patch('devops.helpers.ssh_client.logger', autospec=True)
@mock.patch(
    'paramiko.AutoAddPolicy', autospec=True, return_value='AutoAddPolicy')
@mock.patch('paramiko.SSHClient', autospec=True)
class TestSftp(unittest.TestCase):
    def tearDown(self):
        ssh_client.SSHClient._clear_cache()

    @staticmethod
    def prepare_sftp_file_tests(client):
        _ssh = mock.Mock()
        client.return_value = _ssh
        _sftp = mock.Mock()
        open_sftp = mock.Mock(parent=_ssh, return_value=_sftp)
        _ssh.attach_mock(open_sftp, 'open_sftp')

        # noinspection PyTypeChecker
        ssh = ssh_client.SSHClient(
            host=host,
            port=port,
            auth=ssh_client.SSHAuth(
                username=username,
                password=password
            ))
        return ssh, _sftp

    def test_exists(self, client, policy, logger):
        ssh, _sftp = self.prepare_sftp_file_tests(client)
        lstat = mock.Mock()
        _sftp.attach_mock(lstat, 'lstat')
        dst = '/etc'

        # noinspection PyTypeChecker
        result = ssh.exists(dst)
        self.assertTrue(result)
        lstat.assert_called_once_with(dst)

        # Negative scenario
        lstat.reset_mock()
        lstat.side_effect = IOError

        # noinspection PyTypeChecker
        result = ssh.exists(dst)
        self.assertFalse(result)
        lstat.assert_called_once_with(dst)

    def test_stat(self, client, policy, logger):
        ssh, _sftp = self.prepare_sftp_file_tests(client)
        stat = mock.Mock()
        _sftp.attach_mock(stat, 'stat')
        stat.return_value = paramiko.sftp_attr.SFTPAttributes()
        stat.return_value.st_size = 0
        stat.return_value.st_uid = 0
        stat.return_value.st_gid = 0
        dst = '/etc/passwd'

        # noinspection PyTypeChecker
        result = ssh.stat(dst)
        self.assertEqual(result.st_size, 0)
        self.assertEqual(result.st_uid, 0)
        self.assertEqual(result.st_gid, 0)

    def test_isfile(self, client, policy, logger):
        class Attrs(object):
            def __init__(self, mode):
                self.st_mode = mode

        ssh, _sftp = self.prepare_sftp_file_tests(client)
        lstat = mock.Mock()
        _sftp.attach_mock(lstat, 'lstat')
        lstat.return_value = Attrs(stat.S_IFREG)
        dst = '/etc/passwd'

        # noinspection PyTypeChecker
        result = ssh.isfile(dst)
        self.assertTrue(result)
        lstat.assert_called_once_with(dst)

        # Negative scenario
        lstat.reset_mock()
        lstat.return_value = Attrs(stat.S_IFDIR)

        # noinspection PyTypeChecker
        result = ssh.isfile(dst)
        self.assertFalse(result)
        lstat.assert_called_once_with(dst)

        lstat.reset_mock()
        lstat.side_effect = IOError

        # noinspection PyTypeChecker
        result = ssh.isfile(dst)
        self.assertFalse(result)
        lstat.assert_called_once_with(dst)

    def test_isdir(self, client, policy, logger):
        class Attrs(object):
            def __init__(self, mode):
                self.st_mode = mode

        ssh, _sftp = self.prepare_sftp_file_tests(client)
        lstat = mock.Mock()
        _sftp.attach_mock(lstat, 'lstat')
        lstat.return_value = Attrs(stat.S_IFDIR)
        dst = '/etc/passwd'

        # noinspection PyTypeChecker
        result = ssh.isdir(dst)
        self.assertTrue(result)
        lstat.assert_called_once_with(dst)

        # Negative scenario
        lstat.reset_mock()
        lstat.return_value = Attrs(stat.S_IFREG)

        # noinspection PyTypeChecker
        result = ssh.isdir(dst)
        self.assertFalse(result)
        lstat.assert_called_once_with(dst)

        lstat.reset_mock()
        lstat.side_effect = IOError
        # noinspection PyTypeChecker
        result = ssh.isdir(dst)
        self.assertFalse(result)
        lstat.assert_called_once_with(dst)

    @mock.patch('devops.helpers.ssh_client.SSHClient.exists')
    @mock.patch('devops.helpers.ssh_client.SSHClient.execute')
    def test_mkdir(self, execute, exists, client, policy, logger):
        exists.side_effect = [False, True]

        dst = '~/tst'

        # noinspection PyTypeChecker
        ssh = ssh_client.SSHClient(
            host=host,
            port=port,
            auth=ssh_client.SSHAuth(
                username=username,
                password=password
            ))

        # Path not exists
        # noinspection PyTypeChecker
        ssh.mkdir(dst)
        exists.assert_called_once_with(dst)
        execute.assert_called_once_with("mkdir -p {}\n".format(dst))

        # Path exists
        exists.reset_mock()
        execute.reset_mock()

        # noinspection PyTypeChecker
        ssh.mkdir(dst)
        exists.assert_called_once_with(dst)
        execute.assert_not_called()

    @mock.patch('devops.helpers.ssh_client.SSHClient.execute')
    def test_rm_rf(self, execute, client, policy, logger):
        dst = '~/tst'

        # noinspection PyTypeChecker
        ssh = ssh_client.SSHClient(
            host=host,
            port=port,
            auth=ssh_client.SSHAuth(
                username=username,
                password=password
            ))

        # Path not exists
        # noinspection PyTypeChecker
        ssh.rm_rf(dst)
        execute.assert_called_once_with("rm -rf {}".format(dst))

    def test_open(self, client, policy, logger):
        ssh, _sftp = self.prepare_sftp_file_tests(client)
        fopen = mock.Mock(return_value=True)
        _sftp.attach_mock(fopen, 'open')

        dst = '/etc/passwd'
        mode = 'r'
        # noinspection PyTypeChecker
        result = ssh.open(dst)
        fopen.assert_called_once_with(dst, mode)
        self.assertTrue(result)

    @mock.patch('devops.helpers.ssh_client.SSHClient.exists')
    @mock.patch('os.path.exists', autospec=True)
    @mock.patch('devops.helpers.ssh_client.SSHClient.isdir')
    @mock.patch('os.path.isdir', autospec=True)
    def test_download(
            self,
            isdir, remote_isdir, exists, remote_exists, client, policy, logger
    ):
        ssh, _sftp = self.prepare_sftp_file_tests(client)
        isdir.return_value = True
        exists.side_effect = [True, False, False]
        remote_isdir.side_effect = [False, False, True]
        remote_exists.side_effect = [True, False, False]

        dst = '/etc/environment'
        target = '/tmp/environment'
        # noinspection PyTypeChecker
        result = ssh.download(destination=dst, target=target)
        self.assertTrue(result)
        isdir.assert_called_once_with(target)
        exists.assert_called_once_with(posixpath.join(
            target, path.basename(dst)))
        remote_isdir.assert_called_once_with(dst)
        remote_exists.assert_called_once_with(dst)
        _sftp.assert_has_calls((
            mock.call.get(dst, posixpath.join(target, path.basename(dst))),
        ))

        # Negative scenarios
        logger.reset_mock()
        # noinspection PyTypeChecker
        result = ssh.download(destination=dst, target=target)
        logger.assert_has_calls((
            mock.call.debug(
                "Copying '%s' -> '%s' from remote to local host",
                '/etc/environment',
                '/tmp/environment'),
            mock.call.debug(
                "Can't download %s because it doesn't exist",
                '/etc/environment'
            ),
        ))
        self.assertFalse(result)

        logger.reset_mock()
        # noinspection PyTypeChecker
        ssh.download(destination=dst, target=target)
        logger.assert_has_calls((
            mock.call.debug(
                "Copying '%s' -> '%s' from remote to local host",
                '/etc/environment',
                '/tmp/environment'),
            mock.call.debug(
                "Can't download %s because it is a directory",
                '/etc/environment'
            ),
        ))

    @mock.patch('devops.helpers.ssh_client.SSHClient.isdir')
    @mock.patch('os.path.isdir', autospec=True)
    def test_upload_file(
            self, isdir, remote_isdir, client, policy, logger
    ):
        ssh, _sftp = self.prepare_sftp_file_tests(client)
        isdir.return_value = False
        remote_isdir.return_value = False
        target = '/etc/environment'
        source = '/tmp/environment'

        # noinspection PyTypeChecker
        ssh.upload(source=source, target=target)
        isdir.assert_called_once_with(source)
        remote_isdir.assert_called_once_with(target)
        _sftp.assert_has_calls((
            mock.call.put(source, target),
        ))

    @mock.patch('devops.helpers.ssh_client.SSHClient.exists')
    @mock.patch('devops.helpers.ssh_client.SSHClient.mkdir')
    @mock.patch('os.walk')
    @mock.patch('devops.helpers.ssh_client.SSHClient.isdir')
    @mock.patch('os.path.isdir', autospec=True)
    def test_upload_dir(
            self,
            isdir, remote_isdir, walk, mkdir, exists,
            client, policy, logger
    ):
        ssh, _sftp = self.prepare_sftp_file_tests(client)
        isdir.return_value = True
        remote_isdir.return_value = True
        exists.return_value = True
        target = '/etc'
        source = '/tmp/bash'
        filename = 'bashrc'
        walk.return_value = (source, '', [filename]),
        expected_path = posixpath.join(target, path.basename(source))
        expected_file = posixpath.join(expected_path, filename)

        # noinspection PyTypeChecker
        ssh.upload(source=source, target=target)
        isdir.assert_called_once_with(source)
        remote_isdir.assert_called_once_with(target)
        mkdir.assert_called_once_with(expected_path)
        exists.assert_called_once_with(expected_file)
        _sftp.assert_has_calls((
            mock.call.unlink(expected_file),
            mock.call.put(posixpath.join(source, filename), expected_file),
        ))
