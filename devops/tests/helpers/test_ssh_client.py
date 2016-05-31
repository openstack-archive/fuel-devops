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

# pylint: disable=no-self-use

from contextlib import closing
from os.path import basename
import posixpath
import stat
from unittest import TestCase

import mock
import paramiko
# noinspection PyUnresolvedReferences
from six.moves import cStringIO
from six import PY2

from devops.error import DevopsCalledProcessError
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


@mock.patch('devops.helpers.ssh_client.logger', autospec=True)
@mock.patch(
    'paramiko.AutoAddPolicy', autospec=True, return_value='AutoAddPolicy')
@mock.patch('paramiko.SSHClient', autospec=True)
class TestSSHClient(TestCase):
    def check_defaults(
            self, obj, host, port, username, password, private_keys):
        self.assertEqual(obj.host, host)
        self.assertEqual(obj.port, port)
        self.assertEqual(obj.username, username)
        self.assertEqual(obj.password, password)
        self.assertEqual(obj.private_keys, private_keys)

    def test_init_passwd(self, client, policy, logger):
        _ssh = mock.call()

        ssh = SSHClient(
            host=host,
            port=port,
            username=username,
            password=password,
            private_keys=private_keys)

        client.assert_called_once()
        policy.assert_called_once()

        expected_calls = [
            _ssh,
            _ssh.set_missing_host_key_policy('AutoAddPolicy'),
            _ssh.connect(
                host, password=password,
                port=port, username=username),
            _ssh.open_sftp()
        ]

        self.assertIn(expected_calls, client.mock_calls)

        self.check_defaults(ssh, host, port, username, password, private_keys)
        self.assertIsNone(ssh.private_key)
        self.assertIsNone(ssh.public_key)

        self.assertIn(
            mock.call.debug("Connect to '{0}:{1}' as '{2}:{3}'".format(
                host, port, username, password
            )),
            logger.mock_calls
        )
        sftp = ssh._sftp
        self.assertEqual(sftp, client().open_sftp())

    def test_init_keys(self, client, policy, logger):
        _ssh = mock.call()

        private_keys = gen_private_keys(1)

        ssh = SSHClient(
            host=host,
            port=port,
            username=username,
            password=password,
            private_keys=private_keys)

        client.assert_called_once()
        policy.assert_called_once()

        expected_calls = [
            _ssh,
            _ssh.set_missing_host_key_policy('AutoAddPolicy'),
            _ssh.connect(
                host, password=password, pkey=private_keys[0],
                port=port, username=username),
            _ssh.open_sftp()
        ]

        self.assertIn(expected_calls, client.mock_calls)

        self.check_defaults(ssh, host, port, username, password, private_keys)
        self.assertEqual(ssh.private_key, private_keys[0])
        self.assertEqual(ssh.public_key, gen_public_key(private_keys[0]))

        self.assertIn(
            mock.call.debug("Connect to '{0}:{1}' as '{2}:{3}'".format(
                host, port, username, password
            )),
            logger.mock_calls
        )

    def test_init_as_context(self, client, policy, logger):
        _ssh = mock.call()

        private_keys = gen_private_keys(1)

        with SSHClient(
                host=host,
                port=port,
                username=username,
                password=password,
                private_keys=private_keys) as ssh:

            client.assert_called_once()
            policy.assert_called_once()

            expected_calls = [
                _ssh,
                _ssh.set_missing_host_key_policy('AutoAddPolicy'),
                _ssh.connect(
                    host, password=password, pkey=private_keys[0],
                    port=port, username=username),
                _ssh.open_sftp()
            ]

            self.assertIn(expected_calls, client.mock_calls)

            self.check_defaults(ssh, host, port, username, password,
                                private_keys)

            self.assertIn(
                mock.call.debug("Connect to '{0}:{1}' as '{2}:{3}'".format(
                    host, port, username, password
                )),
                logger.mock_calls
            )

    def test_init_fail_sftp(self, client, policy, logger):
        _ssh = mock.Mock()
        client.return_value = _ssh
        open_sftp = mock.Mock(parent=_ssh, side_effect=paramiko.SSHException)
        _ssh.attach_mock(open_sftp, 'open_sftp')
        warning = mock.Mock(parent=logger)
        logger.attach_mock(warning, 'warning')

        ssh = SSHClient(
            host=host,
            port=port,
            username=username,
            password=password,
            private_keys=private_keys)

        client.assert_called_once()
        policy.assert_called_once()

        self.check_defaults(ssh, host, port, username, password, private_keys)

        warning.assert_called_once_with(
            'SFTP enable failed! SSH only is accessible.'
        )

        with self.assertRaises(paramiko.SSHException):
            # pylint: disable=pointless-statement
            # noinspection PyStatementEffect
            ssh._sftp
            # pylint: enable=pointless-statement

        warning.assert_has_calls([
            mock.call('SFTP enable failed! SSH only is accessible.'),
            mock.call('SFTP is not connected, try to reconnect'),
            mock.call('SFTP enable failed! SSH only is accessible.')])

        # Unblock sftp connection
        # (reset_mock is not possible to use in this case)
        _sftp = mock.Mock()
        open_sftp = mock.Mock(parent=_ssh, return_value=_sftp)
        _ssh.attach_mock(open_sftp, 'open_sftp')
        sftp = ssh._sftp
        self.assertEqual(sftp, _sftp)

    def init_ssh(self, client, policy, logger):
        ssh = SSHClient(
            host=host,
            port=port,
            username=username,
            password=password,
            private_keys=private_keys)

        client.assert_called_once()
        policy.assert_called_once()

        self.assertIn(
            mock.call.debug("Connect to '{0}:{1}' as '{2}:{3}'".format(
                host, port, username, password
            )),
            logger.mock_calls
        )
        return ssh


@mock.patch('devops.helpers.ssh_client.logger', autospec=True)
@mock.patch(
    'paramiko.AutoAddPolicy', autospec=True, return_value='AutoAddPolicy')
@mock.patch('paramiko.SSHClient', autospec=True)
class TestExecute(TestCase):
    @staticmethod
    def get_ssh():
        """SSHClient object builder for execution tests

        :rtype: SSHClient
        """
        return SSHClient(
            host=host,
            port=port,
            username=username,
            password=password
            )

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
            mock.call.exec_command('sudo -S bash -c "{}\n"'.format(command))
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
            mock.call.exec_command('sudo -S bash -c "{}\n"'.format(command))
        ))
        self.assertIn(
            mock.call.debug(
                "Executing command: '{}'".format(command.rstrip())),
            logger.mock_calls
        )

    def test_execute_async_sudo_password(
            self, client, policy, logger):
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
        stdin.assert_has_calls((mock.call.flush(), ))

        self.assertIn(chan, result)
        chan.assert_has_calls((
            mock.call.makefile('wb'),
            mock.call.makefile('rb'),
            mock.call.makefile_stderr('rb'),
            mock.call.exec_command('sudo -S bash -c "{}\n"'.format(command))
        ))
        self.assertIn(
            mock.call.debug(
                "Executing command: '{}'".format(command.rstrip())),
            logger.mock_calls
        )

    @staticmethod
    def get_patched_execute_async_retval(ec=0, stderr_val=True):
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
        return chan, '', stderr, stdout

    @mock.patch(
        'devops.helpers.ssh_client.SSHClient.execute_async')
    def test_execute(self, execute_async, client, policy, logger):
        chan, _stdin, stderr, stdout = self.get_patched_execute_async_retval()
        execute_async.return_value = chan, _stdin, stderr, stdout

        stderr_lst = stderr.readlines()
        stdout_lst = stdout.readlines()

        expected = {
            'exit_code': chan.recv_exit_status(),
            'stderr': stderr_lst,
            'stdout': stdout_lst}
        if PY2:
            expected['stderr_str'] = b''.join(stderr_lst).strip()
            expected['stdout_str'] = b''.join(stdout_lst).strip()
        else:
            expected['stderr_str'] = b''.join(stderr_lst).strip().decode(
                encoding='utf-8')
            expected['stdout_str'] = b''.join(stdout_lst).strip().decode(
                encoding='utf-8')

        ssh = self.get_ssh()

        logger.reset_mock()

        result = ssh.execute(command=command, verbose=True)

        self.assertEqual(
            result,
            expected
        )
        execute_async.assert_called_once_with(command)
        chan.assert_has_calls((
            mock.call.recv_exit_status(),
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
    def test_execute_together(self, execute_async, client, policy, logger):
        chan, _stdin, stderr, stdout = self.get_patched_execute_async_retval()
        execute_async.return_value = chan, _stdin, stderr, stdout

        stderr_lst = stderr.readlines()
        stdout_lst = stdout.readlines()

        expected = {
            'exit_code': chan.recv_exit_status(),
            'stderr': stderr_lst,
            'stdout': stdout_lst}
        if PY2:
            expected['stderr_str'] = b''.join(stderr_lst).strip()
            expected['stdout_str'] = b''.join(stdout_lst).strip()
        else:
            expected['stderr_str'] = b''.join(stderr_lst).strip().decode(
                encoding='utf-8')
            expected['stdout_str'] = b''.join(stdout_lst).strip().decode(
                encoding='utf-8')

        host2 = '127.0.0.2'

        ssh = self.get_ssh()
        ssh2 = SSHClient(
            host=host2,
            port=port,
            username=username,
            password=password
            )

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

        result = ssh.check_call(command=command, verbose=verbose)
        execute.assert_called_once_with(command, verbose)
        self.assertEqual(result, return_value)

        exit_code = 1
        return_value['exit_code'] = exit_code
        execute.reset_mock()
        execute.return_value = return_value
        with self.assertRaises(DevopsCalledProcessError):
            ssh.check_call(command=command, verbose=verbose)
        execute.assert_called_once_with(command, verbose)

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
            command=command, verbose=verbose, raise_on_err=raise_on_err)
        check_call.assert_called_once_with(
            command, verbose, raise_on_err=raise_on_err)
        self.assertEqual(result, return_value)

        return_value['stderr_str'] = '0\n1'
        return_value['stderr'] = [b' \n', b'0\n', b'1\n', b' \n']

        check_call.reset_mock()
        check_call.return_value = return_value
        with self.assertRaises(DevopsCalledProcessError):
            ssh.check_stderr(
                command=command, verbose=verbose, raise_on_err=raise_on_err)
        check_call.assert_called_once_with(
            command, verbose, raise_on_err=raise_on_err)


@mock.patch('devops.helpers.ssh_client.logger', autospec=True)
@mock.patch(
    'paramiko.AutoAddPolicy', autospec=True, return_value='AutoAddPolicy')
@mock.patch('paramiko.SSHClient', autospec=True)
@mock.patch('paramiko.Transport', autospec=True)
class TestExecuteThrowHost(TestCase):
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

        return (
            open_session, transport, channel, get_transport,
            open_channel, intermediate_channel
        )

    def test_execute_through_host_no_creds(
            self, transp, client, policy, logger):
        target = '127.0.0.2'
        exit_code = 0
        return_value = {
            'stderr_str': '0\n1',
            'stdout_str': '2\n3',
            'exit_code': exit_code,
            'stderr': [b' \n', b'0\n', b'1\n', b' \n'],
            'stdout': [b' \n', b'2\n', b'3\n', b' \n']}

        (
            open_session, transport, channel, get_transport,
            open_channel, intermediate_channel
        ) = self.prepare_execute_through_host(
            transp, client, exit_code=exit_code)

        ssh = SSHClient(
            host=host,
            port=port,
            username=username,
            password=password
            )

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
            mock.call.recv_exit_status(),
            mock.call.close()
        ))

    def test_execute_through_host_auth(
            self, transp, client, policy, logger):
        _login = 'cirros'
        _password = 'cubswin:)'

        target = '127.0.0.2'
        exit_code = 0
        return_value = {
            'stderr_str': '0\n1',
            'stdout_str': '2\n3',
            'exit_code': exit_code,
            'stderr': [b' \n', b'0\n', b'1\n', b' \n'],
            'stdout': [b' \n', b'2\n', b'3\n', b' \n']}

        (
            open_session, transport, channel, get_transport,
            open_channel, intermediate_channel
        ) = self.prepare_execute_through_host(
            transp, client, exit_code=exit_code)

        ssh = SSHClient(
            host=host,
            port=port,
            username=username,
            password=password
            )

        result = ssh.execute_through_host(
            target, command,
            username=_login, password=_password)
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
            mock.call.recv_exit_status(),
            mock.call.close()
        ))


@mock.patch('devops.helpers.ssh_client.logger', autospec=True)
@mock.patch(
    'paramiko.AutoAddPolicy', autospec=True, return_value='AutoAddPolicy')
@mock.patch('paramiko.SSHClient', autospec=True)
class TestSftp(TestCase):
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
            username=username,
            password=password
            )
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
            username=username,
            password=password
            )

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
            username=username,
            password=password
            )

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
