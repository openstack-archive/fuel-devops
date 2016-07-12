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
from contextlib import closing
from os.path import basename
import posixpath
import stat
from unittest import TestCase

import mock
import paramiko
# noinspection PyUnresolvedReferences
from six.moves import cStringIO

from devops.error import DevopsCalledProcessError
from devops.error import TimeoutError
from devops.helpers.exec_result import ExecResult
from devops.helpers.ssh_client import SSHAuth
from devops.helpers.ssh_client import SSHClient


def gen_private_keys(amount=1):
    keys = []
    for _ in range(amount):
        keys.append(paramiko.RSAKey.generate(1024))
    return keys


def gen_public_key(private_key=None):
    if private_key is None:
        private_key = paramiko.RSAKey.generate(1024)
    return '{0} {1}'.format(private_key.get_name(), private_key.get_base64())


host = '127.0.0.1'
port = 22
username = 'user'
password = 'pass'
private_keys = []
command = 'ls ~ '
encoded_cmd = base64.b64encode(
    "{}\n".format(command).encode('utf-8')
).decode('utf-8')


class TestSSHAuth(TestCase):
    def tearDown(self):
        SSHClient._clear_cache()

    def init_checks(self, username=None, password=None, key=None, keys=None):
        """shared positive init checks

        :type username: str
        :type password: str
        :type key: paramiko.RSAKey
        :type keys: list
        """
        auth = SSHAuth(
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
        with closing(cStringIO()) as tgt:
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
                cls=SSHAuth.__name__,
                username=auth.username,
                key=_key,
                keys=_keys
            )
        )
        self.assertEqual(
            str(auth),
            '{cls} for {username}'.format(
                cls=SSHAuth.__name__,
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


@mock.patch('devops.helpers.retry.sleep', autospec=True)
@mock.patch('devops.helpers.ssh_client.logger', autospec=True)
@mock.patch(
    'paramiko.AutoAddPolicy', autospec=True, return_value='AutoAddPolicy')
@mock.patch('paramiko.SSHClient', autospec=True)
class TestSSHClientInit(TestCase):
    def tearDown(self):
        SSHClient._clear_cache()

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
        :type auth: SSHAuth
        """
        _ssh = mock.call()

        ssh = SSHClient(
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
                SSHAuth(
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

    def test_init_host(self, client, policy, logger, sleep):
        """Test with host only set"""
        self.init_checks(
            client, policy, logger,
            host=host)

    def test_init_alternate_port(self, client, policy, logger, sleep):
        """Test with alternate port"""
        self.init_checks(
            client, policy, logger,
            host=host,
            port=2222
        )

    def test_init_username(self, client, policy, logger, sleep):
        """Test with username only set from creds"""
        self.init_checks(
            client, policy, logger,
            host=host,
            username=username
        )

    def test_init_username_password(self, client, policy, logger, sleep):
        """Test with username and password set from creds"""
        self.init_checks(
            client, policy, logger,
            host=host,
            username=username,
            password=password
            )

    def test_init_username_password_empty_keys(
            self, client, policy, logger, sleep):
        """Test with username, password and empty keys set from creds"""
        self.init_checks(
            client, policy, logger,
            host=host,
            username=username,
            password=password,
            private_keys=[]
        )

    def test_init_username_single_key(self, client, policy, logger, sleep):
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

    def test_init_username_password_single_key(
            self, client, policy, logger, sleep):
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

    def test_init_username_multiple_keys(self, client, policy, logger, sleep):
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
            self, client, policy, logger, sleep):
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

    def test_init_auth(
            self, client, policy, logger, sleep):
        self.init_checks(
            client, policy, logger,
            host=host,
            auth=SSHAuth(
                username=username,
                password=password,
                key=gen_private_keys(1).pop()
            )
        )

    def test_init_auth_break(
            self, client, policy, logger, sleep):
        self.init_checks(
            client, policy, logger,
            host=host,
            username='Invalid',
            password='Invalid',
            private_keys=gen_private_keys(1),
            auth=SSHAuth(
                username=username,
                password=password,
                key=gen_private_keys(1).pop()
            )
        )

    def test_init_context(
            self, client, policy, logger, sleep):
        with SSHClient(host=host, auth=SSHAuth()) as ssh:
            client.assert_called_once()
            policy.assert_called_once()

            logger.assert_not_called()

            self.assertEqual(ssh.auth, SSHAuth())

            sftp = ssh._sftp
            self.assertEqual(sftp, client().open_sftp())

            self.assertEqual(ssh._ssh, client())

            self.assertEqual(ssh.hostname, host)
            self.assertEqual(ssh.port, port)

    def test_init_clear_failed(
            self, client, policy, logger, sleep):
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

        ssh = SSHClient(host=host, auth=SSHAuth())
        client.assert_called_once()
        policy.assert_called_once()

        logger.assert_not_called()

        self.assertEqual(ssh.auth, SSHAuth())

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

    def test_init_reconnect(
            self, client, policy, logger, sleep):
        """Test reconnect

        :type client: mock.Mock
        :type policy: mock.Mock
        :type logger: mock.Mock
        """
        ssh = SSHClient(host=host, auth=SSHAuth())
        client.assert_called_once()
        policy.assert_called_once()

        logger.assert_not_called()

        self.assertEqual(ssh.auth, SSHAuth())

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

        self.assertEqual(ssh.auth, SSHAuth())

        sftp = ssh._sftp
        self.assertEqual(sftp, client().open_sftp())

        self.assertEqual(ssh._ssh, client())

    def test_init_password_required(
            self, client, policy, logger, sleep):
        connect = mock.Mock(side_effect=paramiko.PasswordRequiredException)
        _ssh = mock.Mock()
        _ssh.attach_mock(connect, 'connect')
        client.return_value = _ssh

        with self.assertRaises(paramiko.PasswordRequiredException):
            SSHClient(host=host, auth=SSHAuth())
        logger.assert_has_calls((
            mock.call.exception('No password has been set!'),
        ))

    def test_init_password_broken(
            self, client, policy, logger, sleep):
        connect = mock.Mock(side_effect=paramiko.PasswordRequiredException)
        _ssh = mock.Mock()
        _ssh.attach_mock(connect, 'connect')
        client.return_value = _ssh

        with self.assertRaises(paramiko.PasswordRequiredException):
            SSHClient(host=host, auth=SSHAuth(password=password))

        logger.assert_has_calls((
            mock.call.critical(
                'Unexpected PasswordRequiredException, '
                'when password is set!'
            ),
        ))

    def test_init_auth_impossible_password(
            self, client, policy, logger, sleep):
        connect = mock.Mock(side_effect=paramiko.AuthenticationException)

        _ssh = mock.Mock()
        _ssh.attach_mock(connect, 'connect')
        client.return_value = _ssh

        with self.assertRaises(paramiko.AuthenticationException):
            SSHClient(host=host, auth=SSHAuth(password=password))

        logger.assert_has_calls(
            (
                mock.call.exception(
                    'Connection using stored authentication info failed!'),
            ) * 3
        )

    def test_init_auth_impossible_key(
            self, client, policy, logger, sleep):
        connect = mock.Mock(side_effect=paramiko.AuthenticationException)

        _ssh = mock.Mock()
        _ssh.attach_mock(connect, 'connect')
        client.return_value = _ssh

        with self.assertRaises(paramiko.AuthenticationException):
            SSHClient(
                host=host,
                auth=SSHAuth(key=gen_private_keys(1).pop())
            )

        logger.assert_has_calls(
            (
                mock.call.exception(
                    'Connection using stored authentication info failed!'),
            ) * 3
        )

    def test_init_auth_pass_no_key(
            self, client, policy, logger, sleep):
        connect = mock.Mock(
            side_effect=[
                paramiko.AuthenticationException,
                mock.Mock()
            ])

        _ssh = mock.Mock()
        _ssh.attach_mock(connect, 'connect')
        client.return_value = _ssh
        key = gen_private_keys(1).pop()

        ssh = SSHClient(
            host=host,
            auth=SSHAuth(
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
            SSHAuth(
                username=username,
                password=password,
                keys=[key]
            )
        )

        sftp = ssh._sftp
        self.assertEqual(sftp, client().open_sftp())

        self.assertEqual(ssh._ssh, client())

    def test_init_auth_brute_impossible(
            self, client, policy, logger, sleep):
        connect = mock.Mock(side_effect=paramiko.AuthenticationException)

        _ssh = mock.Mock()
        _ssh.attach_mock(connect, 'connect')
        client.return_value = _ssh

        with self.assertRaises(paramiko.AuthenticationException):
            SSHClient(
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

    def test_init_no_sftp(
            self, client, policy, logger, sleep):
        open_sftp = mock.Mock(side_effect=paramiko.SSHException)

        _ssh = mock.Mock()
        _ssh.attach_mock(open_sftp, 'open_sftp')
        client.return_value = _ssh

        ssh = SSHClient(host=host, auth=SSHAuth(password=password))

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

    def test_init_sftp_repair(
            self, client, policy, logger, sleep):
        _sftp = mock.Mock()
        open_sftp = mock.Mock(
            side_effect=[
                paramiko.SSHException,
                _sftp, _sftp])

        _ssh = mock.Mock()
        _ssh.attach_mock(open_sftp, 'open_sftp')
        client.return_value = _ssh

        ssh = SSHClient(host=host, auth=SSHAuth(password=password))

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

    @mock.patch('devops.helpers.ssh_client.ExecResult', autospec=True)
    def test_init_memorize(self, Result, client, policy, logger, sleep):
        port1 = 2222
        host1 = '127.0.0.2'

        # 1. Normal init
        ssh01 = SSHClient(host=host)
        ssh02 = SSHClient(host=host)
        ssh11 = SSHClient(host=host, port=port1)
        ssh12 = SSHClient(host=host, port=port1)
        ssh21 = SSHClient(host=host1)
        ssh22 = SSHClient(host=host1)

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
        SSHClient(host=host, auth=SSHAuth(username=username))

        # Change back: new connection differs from old with the same creds
        ssh004 = SSHAuth(host)
        self.assertFalse(ssh01 is ssh004)

    @mock.patch('devops.helpers.ssh_client.warn')
    def test_init_memorize_close_unused(
            self, warn, client, policy, logger, sleep):
        ssh0 = SSHClient(host=host)
        text = str(ssh0)
        del ssh0  # remove reference - now it's cached and unused
        client.reset_mock()
        logger.reset_mock()
        # New connection on the same host:port with different auth
        ssh1 = SSHClient(host=host, auth=SSHAuth(username=username))
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
        SSHClient._clear_cache()
        logger.assert_has_calls((
            mock.call.debug('Closing {} as unused'.format(text)),
        ))
        client.assert_has_calls((
            mock.call().close(),
        ))

    @mock.patch(
        'devops.helpers.ssh_client.SSHClient.execute')
    def test_init_memorize_reconnect(
            self, execute, client, policy, logger, sleep):
        execute.side_effect = paramiko.SSHException
        SSHClient(host=host)
        client.reset_mock()
        policy.reset_mock()
        logger.reset_mock()
        SSHClient(host=host)
        client.assert_called_once()
        policy.assert_called_once()

    @mock.patch('devops.helpers.ssh_client.warn')
    def test_init_clear(self, warn, client, policy, logger, sleep):
        ssh01 = SSHClient(host=host, auth=SSHAuth())

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

    @mock.patch('devops.helpers.ssh_client.warn')
    def test_deprecated_host(self, warn, client, policy, logger, sleep):
        ssh01 = SSHClient(host=host, auth=SSHAuth())
        self.assertEqual(ssh01.host, ssh01.hostname)
        warn.assert_called_once_with(
            'host has been deprecated in favor of hostname',
            DeprecationWarning
        )


@mock.patch('devops.helpers.ssh_client.logger', autospec=True)
@mock.patch(
    'paramiko.AutoAddPolicy', autospec=True, return_value='AutoAddPolicy')
@mock.patch('paramiko.SSHClient', autospec=True)
class TestExecute(TestCase):
    def tearDown(self):
        SSHClient._clear_cache()

    @staticmethod
    def get_ssh():
        """SSHClient object builder for execution tests

        :rtype: SSHClient
        """
        return SSHClient(
            host=host,
            port=port,
            auth=SSHAuth(
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
            mock.call.debug(
                "Executing command: '{}'".format(command.rstrip())),
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
                "eval $(base64 -d <(echo \"{0}\"))'".format(encoded_cmd))
        ))
        self.assertIn(
            mock.call.debug(
                "Executing command: '{}'".format(command.rstrip())),
            logger.mock_calls
        )

    def test_execute_async_with_sudo(self, client, policy, logger):
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
        with SSHClient.get_sudo(ssh):
            self.assertTrue(ssh.sudo_mode)
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
                "eval $(base64 -d <(echo \"{0}\"))'".format(encoded_cmd))
        ))
        self.assertIn(
            mock.call.debug(
                "Executing command: '{}'".format(command.rstrip())),
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
                "eval $(base64 -d <(echo \"{0}\"))'".format(encoded_cmd))
        ))
        self.assertIn(
            mock.call.debug(
                "Executing command: '{}'".format(command.rstrip())),
            logger.mock_calls
        )

    def get_patched_execute_async_retval(self, ec=0, stderr_val=True):
        stderr = mock.Mock()
        stdout = mock.Mock()

        stderr_readlines = mock.Mock(
            return_value=[b' \n', b'0\n', b'1\n', b' \n'] if stderr_val else []
        )
        stdout_readlines = mock.Mock(
            return_value=[b' \n', b'2\n', b'3\n', b' \n'])

        stderr.attach_mock(stderr_readlines, 'readlines')
        stdout.attach_mock(stdout_readlines, 'readlines')

        exit_code = ec
        chan = mock.Mock()
        recv_exit_status = mock.Mock(return_value=exit_code)
        chan.attach_mock(recv_exit_status, 'recv_exit_status')

        wait = mock.Mock()
        status_event = mock.Mock()
        status_event.attach_mock(wait, 'wait')
        chan.attach_mock(status_event, 'status_event')
        chan.configure_mock(exit_status=exit_code)

        return chan, '', stderr, stdout

    @mock.patch(
        'devops.helpers.ssh_client.SSHClient.execute_async')
    def test_execute(self, execute_async, client, policy, logger):
        chan, _stdin, stderr, stdout = self.get_patched_execute_async_retval()
        is_set = mock.Mock(return_value=True)
        chan.status_event.attach_mock(is_set, 'is_set')

        execute_async.return_value = chan, _stdin, stderr, stdout

        stderr_lst = stderr.readlines()
        stdout_lst = stdout.readlines()

        expected = ExecResult(
            cmd=command,
            stderr=stderr_lst,
            stdout=stdout_lst,
            exit_code=0
        )

        ssh = self.get_ssh()

        logger.reset_mock()

        result = ssh.execute(command=command, verbose=True)

        self.assertEqual(
            result,
            expected
        )
        execute_async.assert_called_once_with(command)
        chan.assert_has_calls((
            mock.call.status_event.wait(None),
            mock.call.status_event.is_set(),
            mock.call.close()))
        logger.assert_has_calls((
            mock.call.info(
                '{cmd} execution results:\n'
                'Exit code: {code}\n'
                'STDOUT:\n'
                '{stdout}\n'
                'STDERR:\n'
                '{stderr}'.format(
                    cmd=command,
                    code=result['exit_code'],
                    stdout=result['stdout_str'],
                    stderr=result['stderr_str']
                )),
        ))

    @mock.patch(
        'devops.helpers.ssh_client.SSHClient.execute_async')
    def test_execute_timeout(self, execute_async, client, policy, logger):
        exit_code = 0

        chan, _stdin, stderr, stdout = self.get_patched_execute_async_retval()
        is_set = mock.Mock(return_value=True)
        chan.status_event.attach_mock(is_set, 'is_set')

        execute_async.return_value = chan, _stdin, stderr, stdout

        stderr_lst = stderr.readlines()
        stdout_lst = stdout.readlines()

        expected = ExecResult(
            cmd=command,
            stderr=stderr_lst,
            stdout=stdout_lst,
            exit_code=exit_code
        )

        ssh = self.get_ssh()

        logger.reset_mock()

        result = ssh.execute(command=command, verbose=True, timeout=1)

        self.assertEqual(
            result,
            expected
        )
        execute_async.assert_called_once_with(command)
        chan.assert_has_calls((
            mock.call.status_event.wait(1),
            mock.call.status_event.is_set(),
            mock.call.close()))
        logger.assert_has_calls((
            mock.call.info(
                '{cmd} execution results:\n'
                'Exit code: {code}\n'
                'STDOUT:\n'
                '{stdout}\n'
                'STDERR:\n'
                '{stderr}'.format(
                    cmd=command,
                    code=result['exit_code'],
                    stdout=result['stdout_str'],
                    stderr=result['stderr_str']
                )),
        ))

    @mock.patch(
        'devops.helpers.ssh_client.SSHClient.execute_async')
    def test_execute_timeout_fail(self, execute_async, client, policy, logger):

        chan, _stdin, stderr, stdout = self.get_patched_execute_async_retval()
        is_set = mock.Mock(return_value=False)
        chan.status_event.attach_mock(is_set, 'is_set')

        execute_async.return_value = chan, _stdin, stderr, stdout

        ssh = self.get_ssh()

        logger.reset_mock()

        with self.assertRaises(TimeoutError):
            ssh.execute(command=command, verbose=True, timeout=1)

        execute_async.assert_called_once_with(command)
        chan.assert_has_calls((
            mock.call.status_event.wait(1),
            mock.call.status_event.is_set(),
            mock.call.close()))

    @mock.patch(
        'devops.helpers.ssh_client.SSHClient.execute_async')
    def test_execute_together(self, execute_async, client, policy, logger):
        chan, _stdin, stderr, stdout = self.get_patched_execute_async_retval()
        execute_async.return_value = chan, _stdin, stderr, stdout

        host2 = '127.0.0.2'

        ssh = self.get_ssh()
        ssh2 = SSHClient(
            host=host2,
            port=port,
            auth=SSHAuth(
                username=username,
                password=password
            ))

        remotes = [ssh, ssh2]

        SSHClient.execute_together(
            remotes=remotes, command=command)

        self.assertEqual(execute_async.call_count, len(remotes))
        chan.assert_has_calls((
            mock.call.recv_exit_status(),
            mock.call.close(),
            mock.call.recv_exit_status(),
            mock.call.close()
        ))

        SSHClient.execute_together(
            remotes=remotes, command=command, expected=[1], raise_on_err=False)

        with self.assertRaises(DevopsCalledProcessError):
            SSHClient.execute_together(
                remotes=remotes, command=command, expected=[1])

    @mock.patch(
        'devops.helpers.ssh_client.SSHClient.execute')
    def test_check_call(self, execute, client, policy, logger):
        exit_code = 0
        return_value = {
            'stderr_str': '0\n1',
            'stdout_str': '2\n3',
            'exit_code': exit_code,
            'stderr': [b' \n', b'0\n', b'1\n', b' \n'],
            'stdout': [b' \n', b'2\n', b'3\n', b' \n']}
        execute.return_value = return_value

        verbose = False

        ssh = self.get_ssh()

        result = ssh.check_call(command=command, verbose=verbose, timeout=None)
        execute.assert_called_once_with(command, verbose, None)
        self.assertEqual(result, return_value)

        exit_code = 1
        return_value['exit_code'] = exit_code
        execute.reset_mock()
        execute.return_value = return_value
        with self.assertRaises(DevopsCalledProcessError):
            ssh.check_call(command=command, verbose=verbose, timeout=None)
        execute.assert_called_once_with(command, verbose, None)

    @mock.patch(
        'devops.helpers.ssh_client.SSHClient.check_call')
    def test_check_stderr(self, check_call, client, policy, logger):
        return_value = {
            'stderr_str': '',
            'stdout_str': '2\n3',
            'exit_code': 0,
            'stderr': [],
            'stdout': [b' \n', b'2\n', b'3\n', b' \n']}
        check_call.return_value = return_value

        verbose = False
        raise_on_err = True

        ssh = self.get_ssh()

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
        with self.assertRaises(DevopsCalledProcessError):
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
class TestExecuteThrowHost(TestCase):
    def tearDown(self):
        SSHClient._clear_cache()

    @staticmethod
    def prepare_execute_through_host(transp, client, exit_code):
        intermediate_channel = mock.Mock()

        open_channel = mock.Mock(return_value=intermediate_channel)
        intermediate_transport = mock.Mock()
        intermediate_transport.attach_mock(open_channel, 'open_channel')
        get_transport = mock.Mock(return_value=intermediate_transport)

        _ssh = mock.Mock()
        _ssh.attach_mock(get_transport, 'get_transport')
        client.return_value = _ssh

        transport = mock.Mock()
        transp.return_value = transport

        recv_exit_status = mock.Mock(return_value=exit_code)

        makefile = mock.Mock()
        makefile.attach_mock(mock.Mock(
            return_value=[b' \n', b'2\n', b'3\n', b' \n']),
            'readlines')
        makefile_stderr = mock.Mock()
        makefile_stderr.attach_mock(
            mock.Mock(return_value=[b' \n', b'0\n', b'1\n', b' \n']),
            'readlines')
        channel = mock.Mock()
        channel.attach_mock(mock.Mock(return_value=makefile), 'makefile')
        channel.attach_mock(mock.Mock(
            return_value=makefile_stderr), 'makefile_stderr')
        channel.attach_mock(recv_exit_status, 'recv_exit_status')
        open_session = mock.Mock(return_value=channel)
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

        return_value = ExecResult(
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

        ssh = SSHClient(
            host=host,
            port=port,
            auth=SSHAuth(
                username=username,
                password=password
            ))

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
            mock.call.exec_command('ls ~ '),
            mock.call.status_event.wait(None),
            mock.call.status_event.is_set(),
            mock.call.close()
        ))

    def test_execute_through_host_auth(
            self, transp, client, policy, logger):
        _login = 'cirros'
        _password = 'cubswin:)'

        target = '127.0.0.2'
        exit_code = 0

        return_value = ExecResult(
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

        ssh = SSHClient(
            host=host,
            port=port,
            auth=SSHAuth(
                username=username,
                password=password
            ))

        result = ssh.execute_through_host(
            target, command,
            auth=SSHAuth(username=_login, password=_password))
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
            mock.call.exec_command('ls ~ '),
            mock.call.status_event.wait(None),
            mock.call.status_event.is_set(),
            mock.call.close()
        ))


@mock.patch('devops.helpers.ssh_client.logger', autospec=True)
@mock.patch(
    'paramiko.AutoAddPolicy', autospec=True, return_value='AutoAddPolicy')
@mock.patch('paramiko.SSHClient', autospec=True)
class TestSftp(TestCase):
    def tearDown(self):
        SSHClient._clear_cache()

    @staticmethod
    def prepare_sftp_file_tests(client):
        _ssh = mock.Mock()
        client.return_value = _ssh
        _sftp = mock.Mock()
        open_sftp = mock.Mock(parent=_ssh, return_value=_sftp)
        _ssh.attach_mock(open_sftp, 'open_sftp')

        ssh = SSHClient(
            host=host,
            port=port,
            auth=SSHAuth(
                username=username,
                password=password
            ))
        return ssh, _sftp

    def test_exists(self, client, policy, logger):
        ssh, _sftp = self.prepare_sftp_file_tests(client)
        lstat = mock.Mock()
        _sftp.attach_mock(lstat, 'lstat')
        path = '/etc'

        result = ssh.exists(path)
        self.assertTrue(result)
        lstat.assert_called_once_with(path)

        # Negative scenario
        lstat.reset_mock()
        lstat.side_effect = IOError

        result = ssh.exists(path)
        self.assertFalse(result)
        lstat.assert_called_once_with(path)

    def test_isfile(self, client, policy, logger):
        class Attrs(object):
            def __init__(self, mode):
                self.st_mode = mode

        ssh, _sftp = self.prepare_sftp_file_tests(client)
        lstat = mock.Mock()
        _sftp.attach_mock(lstat, 'lstat')
        lstat.return_value = Attrs(stat.S_IFREG)
        path = '/etc/passwd'

        result = ssh.isfile(path)
        self.assertTrue(result)
        lstat.assert_called_once_with(path)

        # Negative scenario
        lstat.reset_mock()
        lstat.return_value = Attrs(stat.S_IFDIR)

        result = ssh.isfile(path)
        self.assertFalse(result)
        lstat.assert_called_once_with(path)

        lstat.reset_mock()
        lstat.side_effect = IOError

        result = ssh.isfile(path)
        self.assertFalse(result)
        lstat.assert_called_once_with(path)

    def test_isdir(self, client, policy, logger):
        class Attrs(object):
            def __init__(self, mode):
                self.st_mode = mode

        ssh, _sftp = self.prepare_sftp_file_tests(client)
        lstat = mock.Mock()
        _sftp.attach_mock(lstat, 'lstat')
        lstat.return_value = Attrs(stat.S_IFDIR)
        path = '/etc/passwd'

        result = ssh.isdir(path)
        self.assertTrue(result)
        lstat.assert_called_once_with(path)

        # Negative scenario
        lstat.reset_mock()
        lstat.return_value = Attrs(stat.S_IFREG)

        result = ssh.isdir(path)
        self.assertFalse(result)
        lstat.assert_called_once_with(path)

        lstat.reset_mock()
        lstat.side_effect = IOError
        result = ssh.isdir(path)
        self.assertFalse(result)
        lstat.assert_called_once_with(path)

    @mock.patch('devops.helpers.ssh_client.SSHClient.exists')
    @mock.patch('devops.helpers.ssh_client.SSHClient.execute')
    def test_mkdir(self, execute, exists, client, policy, logger):
        exists.side_effect = [False, True]

        path = '~/tst'

        ssh = SSHClient(
            host=host,
            port=port,
            auth=SSHAuth(
                username=username,
                password=password
            ))

        # Path not exists
        ssh.mkdir(path)
        exists.assert_called_once_with(path)
        execute.assert_called_once_with("mkdir -p {}\n".format(path))

        # Path exists
        exists.reset_mock()
        execute.reset_mock()

        ssh.mkdir(path)
        exists.assert_called_once_with(path)
        execute.assert_not_called()

    @mock.patch('devops.helpers.ssh_client.SSHClient.execute')
    def test_rm_rf(self, execute, client, policy, logger):
        path = '~/tst'

        ssh = SSHClient(
            host=host,
            port=port,
            auth=SSHAuth(
                username=username,
                password=password
            ))

        # Path not exists
        ssh.rm_rf(path)
        execute.assert_called_once_with("rm -rf {}".format(path))

    def test_open(self, client, policy, logger):
        ssh, _sftp = self.prepare_sftp_file_tests(client)
        fopen = mock.Mock(return_value=True)
        _sftp.attach_mock(fopen, 'open')

        path = '/etc/passwd'
        mode = 'r'
        result = ssh.open(path)
        fopen.assert_called_once_with(path, mode)
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
        result = ssh.download(destination=dst, target=target)
        self.assertTrue(result)
        isdir.assert_called_once_with(target)
        exists.assert_called_once_with(posixpath.join(target, basename(dst)))
        remote_isdir.assert_called_once_with(dst)
        remote_exists.assert_called_once_with(dst)
        _sftp.assert_has_calls((
            mock.call.get(dst, posixpath.join(target, basename(dst))),
        ))

        # Negative scenarios
        logger.reset_mock()
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
        result = ssh.download(destination=dst, target=target)
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
        expected_path = posixpath.join(target, basename(source))
        expected_file = posixpath.join(expected_path, filename)

        ssh.upload(source=source, target=target)
        isdir.assert_called_once_with(source)
        remote_isdir.assert_called_once_with(target)
        mkdir.assert_called_once_with(expected_path)
        exists.assert_called_once_with(expected_file)
        _sftp.assert_has_calls((
            mock.call.unlink(expected_file),
            mock.call.put(posixpath.join(source, filename), expected_file),
        ))
