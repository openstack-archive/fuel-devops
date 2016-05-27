#    Copyright 2013 - 2016 Mirantis, Inc.
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

import os
import posixpath
import stat
from warnings import warn

import paramiko
import six

from devops.error import DevopsCalledProcessError
from devops.helpers.retry import retry
from devops import logger


class SSHAuth(object):
    __slots__ = ['__username', '__password', '__key']

    def __init__(
            self,
            username=None, password=None, key=None):
        """SSH authorisation object

        Used to authorize SSHClient.
        Single SSHAuth object is associated with single host:port.
        Password and key is private, other data is read-only.

        :type username: str
        :type password: str
        :type key: paramiko.RSAKey
        """
        self.__username = username
        self.__password = password
        self.__key = key

    @property
    def username(self):
        """Username for auth

        :rtype: str
        """
        return self.__username

    @property
    def public_key(self):
        """public key for stored private key if presents else None

        :rtype: str
        """
        if self.__key is None:
            return None
        return '{0} {1}'.format(self.__key.get_name(), self.__key.get_base64())

    def enter_password(self, tgt):
        """Enter password to STDIN

        Note: required for 'sudo' call

        :type tgt: file
        :rtype: str
        """
        return tgt.write('{}\n'.format(self.__password))

    def connect(self, client, hostname=None, port=22, log=True):
        """Connect SSH client object using credentials

        :type client:
            paramiko.client.SSHClient
            paramiko.transport.Transport
        :type log: bool
        :raises paramiko.AuthenticationException
        """
        kwargs = {
            'username': self.username,
            'password': self.__password,
            'pkey': self.__key}
        if hostname is not None:
            kwargs['hostname'] = hostname
            kwargs['port'] = port
        try:
            client.connect(**kwargs)
        except paramiko.PasswordRequiredException:
            if self.__password is None:
                logger.exception('No password has been set!')
                raise
            else:
                logger.critical(
                    'Unexpected PasswordRequiredException, '
                    'when password is set!')
                raise
        except paramiko.AuthenticationException:
            if self.__key is None:
                if log:
                    logger.exception(
                        'Connection using stored authentication info failed!')
                raise
            try:
                if log:
                    logger.warning(
                        'Connection using stored authentication info failed! '
                        'Retry without private key...')
                del kwargs['pkey']
                client.connect(**kwargs)
                self.__key = None
                if log:
                    logger.warning(
                        'Private key has been deleted '
                        'from auth info as invalid')
            except paramiko.AuthenticationException:
                if log:
                    logger.exception(
                        'Connection using stored authentication info failed!')
                raise

    def __hash__(self):
        return hash((
            self.__class__,
            self.username,
            self.__password,
            self.__key
        ))

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __repr__(self):
        return (
            '{cls}(username={username}, '
            'password=<*masked*>, key={key})'.format(
                cls=self.__class__.__name__,
                username=self.username,
                key=(
                    None if self.__key is None else
                    '<private for pub: {}>'.format(self.public_key))
            ))

    def __str__(self):
        return (
            '{cls} for {username}'.format(
                cls=self.__class__.__name__,
                username=self.username,
            )
        )


class SSHClient(object):
    __slots__ = [
        '__hostname', '__port', '__auth', '__ssh', '__sftp', 'sudo_mode'
    ]

    class get_sudo(object):
        """Context manager for call commands with sudo"""
        def __init__(self, ssh):
            self.ssh = ssh

        def __enter__(self):
            self.ssh.sudo_mode = True

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.ssh.sudo_mode = False

    def __hash__(self):
        return hash((
            self.__class__,
            self.hostname,
            self.port,
            self.auth))

    def __init__(
            self,
            host, port=22,
            username=None, password=None, private_keys=None,
            auth=None
    ):
        """SSHClient helper

        :type host: str
        :type port: int
        :type username: str
        :type password: str
        :type private_keys: list
        :type auth: SSHAuth
        """
        self.__hostname = host
        self.__port = port

        self.sudo_mode = False
        self.__ssh = None
        self.__sftp = None

        self.__auth = auth

        if auth is None:
            msg = (
                'SSHClient initialization by username/password/private_keys '
                'is deprecated in favor of SSHAuth usage. '
                'Please update your code')
            warn(msg, DeprecationWarning)
            logger.warning(msg)

        if auth is not None:
            self.__connect()
        elif private_keys is None or len(private_keys) == 1:
            self.__auth = SSHAuth(
                username=username,
                password=password,
                key=None if private_keys is None else private_keys[0]
            )
            self.__connect()
        else:
            logger.info(
                'Multiple private keys has been set, using brute-force.')
            auth_list = [
                SSHAuth(
                    username=username,
                    password=password,
                    key=key
                ) for key in private_keys
            ]
            self.__auth = self.__brute_force_connect(auth_list=auth_list)

        self.__connect_sftp()

    @property
    def auth(self):
        """Internal authorisation object

        Attention: this public property is mainly for inheritance,
        debug and information purposes.
        Calls outside SSHClient and child classes is sign of icorrect design.
        Change is completely disallowed.

        :rtype: SSHAuth
        """
        return self.__auth

    @property
    def hostname(self):
        return self.__hostname

    @property
    def port(self):
        return self.__port

    @property
    def _ssh(self):
        """ssh client object getter for inheritance support only

        Attention: ssh client object creation and change
        is allowed only by __init__ and reconnect call.

        :rtype: paramiko.SSHClient
        """
        return self.__ssh

    @retry(count=3, delay=3)
    def __connect(self):
        """Main method for connection open"""
        self.__ssh = paramiko.SSHClient()
        self.__ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.auth.connect(
            client=self.__ssh,
            hostname=self.hostname, port=self.port,
            log=True)

    @retry(count=3, delay=3)
    def __brute_force_connect(self, auth_list):
        """Brute force connection method. Only for legacy use.

        :type auth_list: list
        :rtype: SSHAuth
        :raises: paramiko.AuthenticationException
        """
        self.__ssh = paramiko.SSHClient()
        self.__ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        for auth in auth_list:
            try:
                auth.connect(
                    client=self.__ssh,
                    hostname=self.hostname, port=self.port,
                    log=False)
                return auth
            except paramiko.AuthenticationException:
                continue
        msg = (
            'No any correct authentication credentials accessible:\n'
            '\t{} keys failed\n'
            '\tconnect without private key failed'.format(len(auth_list)))
        logger.critical(msg)
        raise paramiko.AuthenticationException()

    def __connect_sftp(self):
        """SFTP connection opener"""
        try:
            self.__sftp = self.__ssh.open_sftp()
        except paramiko.SSHException:
            logger.warning('SFTP enable failed! SSH only is accessible.')

    @property
    def _sftp(self):
        """SFTP channel access for inheritance

        :raises: paramiko.SSHException
        """
        if self.__sftp is not None:
            return self.__sftp
        logger.warning('SFTP is not connected, try to reconnect')
        self.__connect_sftp()
        if self.__sftp is not None:
            return self.__sftp
        raise paramiko.SSHException('SFTP connection failed')

    def clear(self):
        if self.__ssh is not None:
            try:
                self.__ssh.close()
                self.__sftp = None
            except Exception:
                logger.exception("Could not close ssh connection")
                if self.__sftp is not None:
                    try:
                        self.__sftp.close()
                    except Exception:
                        logger.exception("Could not close sftp connection")

    def __del__(self):
        if self.__ssh is not None:
            self.__ssh.close()
            self.__sftp = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.clear()

    def reconnect(self):
        """Reconnect SSH and SFTP session"""
        self.clear()
        self.__connect()
        self.__connect_sftp()

    def check_call(
            self,
            command, verbose=False,
            expected=None, raise_on_err=True):
        """Execute command and check for return code

        :type command: str
        :type verbose: bool
        :type expected: list
        :type raise_on_err: bool
        :rtype: dict
        :raises: DevopsCalledProcessError
        """
        if expected is None:
            expected = [0]
        ret = self.execute(command, verbose)
        if ret['exit_code'] not in expected and raise_on_err:
            raise DevopsCalledProcessError(
                command, ret['exit_code'],
                expected=expected,
                stdout=ret['stdout_str'],
                stderr=ret['stderr_str'])
        return ret

    def check_stderr(self, command, verbose=False, raise_on_err=True):
        """Execute command expecting return code 0 and empty STDERR

        :type command: str
        :type verbose: bool
        :type raise_on_err: bool
        :rtype: dict
        :raises: DevopsCalledProcessError
        """
        ret = self.check_call(command, verbose, raise_on_err=raise_on_err)
        if ret['stderr']:
            raise DevopsCalledProcessError(command, ret['exit_code'],
                                           stdout=ret['stdout_str'],
                                           stderr=ret['stderr_str'])
        return ret

    @classmethod
    def execute_together(
            cls, remotes, command, expected=None, raise_on_err=True):
        """Execute command on multiple remotes in async mode

        :type remotes: list
        :type command: str
        :type expected: list
        :type raise_on_err: bool
        :raises: DevopsCalledProcessError
        """
        if expected is None:
            expected = [0]
        futures = {}
        errors = {}
        for remote in set(remotes):  # Use distinct remotes
            chan, _, _, _ = remote.execute_async(command)
            futures[remote] = chan
        for remote, chan in futures.items():
            ret = chan.recv_exit_status()
            chan.close()
            if ret not in expected:
                errors[remote.hostname] = ret
        if errors and raise_on_err:
            raise DevopsCalledProcessError(command, errors)

    def execute(self, command, verbose=False):
        """Execute command and wait for return code

        :type command: str
        :type verbose: bool
        :rtype: dict
        """
        chan, _, stderr, stdout = self.execute_async(command)

        # noinspection PyDictCreation
        result = {
            'exit_code': chan.recv_exit_status()
        }
        result['stdout'] = stdout.readlines()
        result['stderr'] = stderr.readlines()

        chan.close()

        result['stdout_str'] = self._get_str_from_list(result['stdout'])
        result['stderr_str'] = self._get_str_from_list(result['stderr'])

        if verbose:
            logger.info(
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
                ))
            logger.info(result['stdout_str'])
            logger.info(result['stderr_str'])

        return result

    @staticmethod
    def _get_str_from_list(src):
        if six.PY2:
            return b''.join(src).strip()
        else:
            return b''.join(src).strip().decode(encoding='utf-8')

    def execute_async(self, command):
        """Execute command in async mode and return channel with IO objects

        :type command: str
        :rtype: tuple
        """
        logger.debug("Executing command: '{}'".format(command.rstrip()))
        chan = self._ssh.get_transport().open_session()
        stdin = chan.makefile('wb')
        stdout = chan.makefile('rb')
        stderr = chan.makefile_stderr('rb')
        cmd = "{}\n".format(command)
        if self.sudo_mode:
            cmd = 'sudo -S bash -c "%s"' % cmd.replace('"', '\\"')
            chan.exec_command(cmd)
            if stdout.channel.closed is False:
                self.auth.enter_password(stdin)
                stdin.flush()
        else:
            chan.exec_command(cmd)
        return chan, stdin, stderr, stdout

    def execute_through_host(
            self,
            hostname,
            cmd,
            auth=None,
            target_port=22):
        """Execute command on remote host throw currently connected host

        :type hostname: str
        :type cmd: str
        :type auth: SSHAuth
        :type target_port: int
        :rtype: dict
        """
        if auth is None:
            auth = self.auth

        intermediate_channel = self._ssh.get_transport().open_channel(
            kind='direct-tcpip',
            dest_addr=(hostname, target_port),
            src_addr=(self.hostname, 0))
        transport = paramiko.Transport(sock=intermediate_channel)

        # start client and authenticate transport
        auth.connect(transport)

        # open ssh session
        channel = transport.open_session()

        # Make proxy objects for read
        stdout = channel.makefile('rb')
        stderr = channel.makefile_stderr('rb')

        logger.info("Executing command: {}".format(cmd))
        channel.exec_command(cmd)

        # TODO(astepanov): make a logic for controlling channel state
        # noinspection PyDictCreation
        result = {}
        result['exit_code'] = channel.recv_exit_status()

        result['stdout'] = stdout.readlines()
        result['stderr'] = stderr.readlines()
        channel.close()

        result['stdout_str'] = self._get_str_from_list(result['stdout'])
        result['stderr_str'] = self._get_str_from_list(result['stderr'])

        return result

    def mkdir(self, path):
        """run 'mkdir -p path' on remote

        :type path: str
        """
        if self.exists(path):
            return
        logger.debug("Creating directory: {}".format(path))
        self.execute("mkdir -p {}\n".format(path))

    def rm_rf(self, path):
        """run 'rm -rf path' on remote

        :type path: str
        """
        logger.debug("rm -rf {}".format(path))
        self.execute("rm -rf {}".format(path))

    def open(self, path, mode='r'):
        """Open file on remote using SFTP session

        :type path: str
        :type mode: str
        :return: file.open() stream
        """
        return self._sftp.open(path, mode)

    def upload(self, source, target):
        """Upload file(s) from source to target using SFTP session

        :type source: str
        :type target: str
        """
        logger.debug("Copying '%s' -> '%s'", source, target)

        if self.isdir(target):
            target = posixpath.join(target, os.path.basename(source))

        source = os.path.expanduser(source)
        if not os.path.isdir(source):
            self._sftp.put(source, target)
            return

        for rootdir, _, files in os.walk(source):
            targetdir = os.path.normpath(
                os.path.join(
                    target,
                    os.path.relpath(rootdir, source))).replace("\\", "/")

            self.mkdir(targetdir)

            for entry in files:
                local_path = os.path.join(rootdir, entry)
                remote_path = posixpath.join(targetdir, entry)
                if self.exists(remote_path):
                    self._sftp.unlink(remote_path)
                self._sftp.put(local_path, remote_path)

    def download(self, destination, target):
        """Download file(s) to target from destination

        :type destination: str
        :type target: str
        :rtype: bool
        """
        logger.debug(
            "Copying '%s' -> '%s' from remote to local host",
            destination, target
        )

        if os.path.isdir(target):
            target = posixpath.join(target, os.path.basename(destination))

        if not self.isdir(destination):
            if self.exists(destination):
                self._sftp.get(destination, target)
            else:
                logger.debug(
                    "Can't download %s because it doesn't exist", destination
                )
        else:
            logger.debug(
                "Can't download %s because it is a directory", destination
            )
        return os.path.exists(target)

    def exists(self, path):
        """Check for file existence using SFTP session

        :type path: str
        :rtype: bool
        """
        try:
            self._sftp.lstat(path)
            return True
        except IOError:
            return False

    def isfile(self, path):
        """Check, that path is file using SFTP session

        :type path: str
        :rtype: bool
        """
        try:
            attrs = self._sftp.lstat(path)
            return attrs.st_mode & stat.S_IFREG != 0
        except IOError:
            return False

    def isdir(self, path):
        """Check, that path is directory using SFTP session

        :type path: str
        :rtype: bool
        """
        try:
            attrs = self._sftp.lstat(path)
            return attrs.st_mode & stat.S_IFDIR != 0
        except IOError:
            return False
