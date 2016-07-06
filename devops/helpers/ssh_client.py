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

from __future__ import unicode_literals

import base64
import os
import posixpath
import stat
from sys import getrefcount
from threading import RLock
from warnings import warn

import paramiko
import six

from devops.error import DevopsCalledProcessError
from devops.error import TimeoutError
from devops.helpers.retry import retry
from devops import logger


class SSHAuth(object):
    __slots__ = ['__username', '__password', '__key', '__keys']

    def __init__(
            self,
            username=None, password=None, key=None, keys=None):
        """SSH authorisation object

        Used to authorize SSHClient.
        Single SSHAuth object is associated with single host:port.
        Password and key is private, other data is read-only.

        :type username: str
        :type password: str
        :type key: paramiko.RSAKey
        :type keys: list
        """
        self.__username = username
        self.__password = password
        self.__key = key
        self.__keys = [None]
        if key is not None:
            self.__keys.append(key)
        if keys is not None:
            for key in keys:
                if key not in self.__keys:
                    self.__keys.append(key)

    @property
    def username(self):
        """Username for auth

        :rtype: str
        """
        return self.__username

    @staticmethod
    def __get_public_key(key):
        """Internal method for get public key from private

        :type key: paramiko.RSAKey
        """
        if key is None:
            return None
        return '{0} {1}'.format(key.get_name(), key.get_base64())

    @property
    def public_key(self):
        """public key for stored private key if presents else None

        :rtype: str
        """
        return self.__get_public_key(self.__key)

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
            'password': self.__password}
        if hostname is not None:
            kwargs['hostname'] = hostname
            kwargs['port'] = port

        keys = [self.__key]
        keys.extend([k for k in self.__keys if k != self.__key])

        for key in keys:
            kwargs['pkey'] = key
            try:
                client.connect(**kwargs)
                if self.__key != key:
                    self.__key = key
                    logger.debug(
                        'Main key has been updated, public key is: \n'
                        '{}'.format(self.public_key))
                return
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
                continue
        msg = 'Connection using stored authentication info failed!'
        if log:
            logger.exception(
                'Connection using stored authentication info failed!')
        raise paramiko.AuthenticationException(msg)

    def __hash__(self):
        return hash((
            self.__class__,
            self.username,
            self.__password,
            tuple(self.__keys)
        ))

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __repr__(self):
        _key = (
            None if self.__key is None else
            '<private for pub: {}>'.format(self.public_key)
        )
        _keys = []
        for k in self.__keys:
            if k == self.__key:
                continue
            _keys.append(
                '<private for pub: {}>'.format(
                    self.__get_public_key(key=k)) if k is not None else None)

        return (
            '{cls}(username={username}, '
            'password=<*masked*>, key={key}, keys={keys})'.format(
                cls=self.__class__.__name__,
                username=self.username,
                key=_key,
                keys=_keys)
        )

    def __str__(self):
        return (
            '{cls} for {username}'.format(
                cls=self.__class__.__name__,
                username=self.username,
            )
        )


class _MemorizedSSH(type):
    """Memorize metaclass for SSHClient

    This class implements caching and managing of SSHClient connections.
    Class is not in public scope: all required interfaces is accessible throw
      SSHClient classmethods.

    Main flow is:
      SSHClient() -> check for cached connection and
        if exists the same: check for alive, reconnect if required and return
        if exists with different credentials: delete and continue processing
        create new connection and cache on success

    Close cached connections is allowed per-client and all stored:
      connection will be closed, but still stored in cache for faster reconnect

    Clear cache is strictly not recommended:
      from this moment all open connections should be managed manually,
      duplicates is possible.
    """
    __cache = {}

    def __call__(
            cls,
            host, port=22,
            username=None, password=None, private_keys=None,
            auth=None
    ):
        """Main memorize method: check for cached instance and return it

        :type host: str
        :type port: int
        :type username: str
        :type password: str
        :type private_keys: list
        :type auth: SSHAuth
        :rtype: SSHClient
        """
        if (host, port) in cls.__cache:
            key = host, port
            if auth is None:
                auth = SSHAuth(
                    username=username, password=password, keys=private_keys)
            if hash((cls, host, port, auth)) == hash(cls.__cache[key]):
                ssh = cls.__cache[key]
                try:
                    ssh.execute('cd ~', timeout=5)
                except (paramiko.SSHException, AttributeError, TimeoutError):
                    logger.debug('Reconnect {}'.format(ssh))
                    ssh.reconnect()
                return ssh
            if getrefcount(cls.__cache[key]) == 2:
                # If we have only cache reference and temporary getrefcount
                # reference: close connection before deletion
                logger.debug('Closing {} as unused'.format(cls.__cache[key]))
                cls.__cache[key].close()
            del cls.__cache[key]
        return super(
            _MemorizedSSH, cls).__call__(
            host=host, port=port,
            username=username, password=password, private_keys=private_keys,
            auth=auth)

    @classmethod
    def record(mcs, ssh):
        """Record SSH client to cache

        :type ssh: SSHClient
        """
        mcs.__cache[(ssh.hostname, ssh.port)] = ssh

    @classmethod
    def clear_cache(mcs):
        """Clear cached connections for initialize new instance on next call"""
        if six.PY3:
            n_count = 3  # cache, ssh, temporary
        else:
            n_count = 4  # cache, values mapping, ssh, temporary
        for ssh in mcs.__cache.values():
            if getrefcount(ssh) == n_count:
                logger.debug('Closing {} as unused'.format(ssh))
                ssh.close()
        mcs.__cache = {}

    @classmethod
    def close_connections(mcs, hostname=None):
        """Close connections for selected or all cached records

        :type hostname: str
        """
        if hostname is None:
            keys = [key for key, ssh in mcs.__cache.items() if ssh.is_alive]
        else:
            keys = [
                (host, port)
                for (host, port), ssh
                in mcs.__cache.items() if host == hostname and ssh.is_alive]
        # raise ValueError(keys)
        for key in keys:
            mcs.__cache[key].close()


class SSHClient(six.with_metaclass(_MemorizedSSH, object)):
    __slots__ = [
        '__hostname', '__port', '__auth', '__ssh', '__sftp', 'sudo_mode',
        '__lock'
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
        self.__lock = RLock()

        self.__hostname = host
        self.__port = port

        self.sudo_mode = False
        self.__ssh = paramiko.SSHClient()
        self.__ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.__sftp = None

        self.__auth = auth

        if auth is None:
            msg = (
                'SSHClient(host={host}, port={port}, username={username}): '
                'initialization by username/password/private_keys '
                'is deprecated in favor of SSHAuth usage. '
                'Please update your code'.format(
                    host=host, port=port, username=username
                ))
            warn(msg, DeprecationWarning)
            logger.debug(msg)

            self.__auth = SSHAuth(
                username=username,
                password=password,
                keys=private_keys
            )

        self.__connect()
        _MemorizedSSH.record(ssh=self)
        if auth is None:
            logger.info(
                '{0}:{1}> SSHAuth was made from old style creds: '
                '{2}'.format(self.hostname, self.port, self.auth))

    @property
    def lock(self):
        return self.__lock

    @property
    def auth(self):
        """Internal authorisation object

        Attention: this public property is mainly for inheritance,
        debug and information purposes.
        Calls outside SSHClient and child classes is sign of incorrect design.
        Change is completely disallowed.

        :rtype: SSHAuth
        """
        return self.__auth

    @property
    def hostname(self):
        """Connected remote host name

        :rtype: str
        """
        return self.__hostname

    @property
    def host(self):
        """Hostname access for backward compatibility

        :rtype: str
        """
        warn(
            'host has been deprecated in favor of hostname',
            DeprecationWarning
        )
        return self.hostname

    @property
    def port(self):
        """Connected remote port number

        :rtype: int
        """
        return self.__port

    @property
    def is_alive(self):
        """Paramiko status: ready to use|reconnect required

        :rtype: bool
        """
        return self.__ssh.get_transport() is not None

    def __repr__(self):
        return '{cls}(host={host}, port={port}, auth={auth!r})'.format(
            cls=self.__class__.__name__, host=self.hostname, port=self.port,
            auth=self.auth
        )

    def __str__(self):
        return '{cls}(host={host}, port={port}) for user {user}'.format(
            cls=self.__class__.__name__, host=self.hostname, port=self.port,
            user=self.auth.username
        )

    @property
    def _ssh(self):
        """ssh client object getter for inheritance support only

        Attention: ssh client object creation and change
        is allowed only by __init__ and reconnect call.

        :rtype: paramiko.SSHClient
        """
        return self.__ssh

    @retry(paramiko.SSHException, count=3, delay=3)
    def __connect(self):
        """Main method for connection open"""
        with self.lock:
            self.auth.connect(
                client=self.__ssh,
                hostname=self.hostname, port=self.port,
                log=True)

    def __connect_sftp(self):
        """SFTP connection opener"""
        with self.lock:
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
        logger.debug('SFTP is not connected, try to connect...')
        self.__connect_sftp()
        if self.__sftp is not None:
            return self.__sftp
        raise paramiko.SSHException('SFTP connection failed')

    def close(self):
        """Close SSH and SFTP sessions"""
        with self.lock:
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

    @staticmethod
    def clear():
        warn(
            "clear is removed: use close() only if it mandatory: "
            "it's automatically called on revert|shutdown|suspend|destroy",
            DeprecationWarning
        )

    @classmethod
    def _clear_cache(cls):
        """Enforce clear memorized records"""
        warn(
            '_clear_cache() is dangerous and not recommended for normal use!',
            Warning
        )
        _MemorizedSSH.clear_cache()

    @classmethod
    def close_connections(cls, hostname=None):
        """Close cached connections: if hostname is not set, then close all

        :type hostname: str
        """
        _MemorizedSSH.close_connections(hostname=hostname)

    def __del__(self):
        """Destructor helper: close channel and threads BEFORE closing others

        Due to threading in paramiko, default destructor could generate asserts
        on close, so we calling channel close before closing main ssh object.
        """
        self.__ssh.close()
        self.__sftp = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def reconnect(self):
        """Reconnect SSH session"""
        with self.lock:
            self.close()

            self.__ssh = paramiko.SSHClient()
            self.__ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            self.__connect()

    def check_call(
            self,
            command, verbose=False, timeout=None,
            expected=None, raise_on_err=True):
        """Execute command and check for return code

        :type command: str
        :type verbose: bool
        :type timeout: int
        :type expected: list
        :type raise_on_err: bool
        :rtype: dict
        :raises: DevopsCalledProcessError
        """
        if expected is None:
            expected = [0]
        ret = self.execute(command, verbose, timeout)
        if ret['exit_code'] not in expected:
            message = (
                "Command '{cmd}' returned exit code {code} while "
                "expected {expected}\n"
                "\tSTDOUT:\n"
                "{stdout}"
                "\n\tSTDERR:\n"
                "{stderr}".format(
                    cmd=command,
                    code=ret['exit_code'],
                    expected=expected,
                    stdout=ret['stdout_str'],
                    stderr=ret['stderr_str']
                ))
            logger.error(message)
            if raise_on_err:
                raise DevopsCalledProcessError(
                    command, ret['exit_code'],
                    expected=expected,
                    stdout=ret['stdout_str'],
                    stderr=ret['stderr_str'])
        return ret

    def check_stderr(
            self,
            command, verbose=False, timeout=None,
            raise_on_err=True):
        """Execute command expecting return code 0 and empty STDERR

        :type command: str
        :type verbose: bool
        :type raise_on_err: bool
        :rtype: dict
        :raises: DevopsCalledProcessError
        """
        ret = self.check_call(
            command, verbose, timeout=timeout, raise_on_err=raise_on_err)
        if ret['stderr']:
            message = (
                "Command '{cmd}' STDERR while not expected\n"
                "\texit code: {code}\n"
                "\tSTDOUT:\n"
                "{stdout}"
                "\n\tSTDERR:\n"
                "{stderr}".format(
                    cmd=command,
                    code=ret['exit_code'],
                    stdout=ret['stdout_str'],
                    stderr=ret['stderr_str']
                ))
            logger.error(message)
            if raise_on_err:
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

    def execute(self, command, verbose=False, timeout=None):
        """Execute command and wait for return code

        :type command: str
        :type verbose: bool
        :type timeout: int
        :rtype: dict
        :raises: TimeoutError
        """
        chan, _, stderr, stdout = self.execute_async(command)

        # Due to not implemented timeout in paramiko.channel.recv_exit_status:
        #   re-implement function using the same calls
        chan.status_event.wait(timeout)
        if chan.status_event.is_set():
            result = {
                'exit_code': chan.exit_status
            }
        else:
            stdout_str = self._get_str_from_list(stdout.readlines())
            stderr_str = self._get_str_from_list(stderr.readlines())
            chan.close()
            status = (
                'Wait for {0} during {1}s: no return code!\n'
                '\tSTDOUT:\n'
                '{2}\n'
                '\tSTDERR"\n'
                '{3}'.format(
                    command, timeout, stdout_str, stderr_str
                )
            )
            raise TimeoutError(status)

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
        else:
            logger.debug(
                '{cmd} execution results: Exit code: {code}'.format(
                    cmd=command,
                    code=result['exit_code']
                )
            )

        return result

    @staticmethod
    def _get_str_from_list(src):
        """Join data in list to the string, with python 2&3 compatibility.

        :type src: list
        :rtype: str
        """
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
            encoded_cmd = base64.b64encode(cmd.encode('utf-8')).decode('utf-8')
            cmd = "sudo -S bash -c 'eval $(base64 -d <(echo \"{0}\"))'".format(
                encoded_cmd
            )
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
        """Execute command on remote host through currently connected host

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

__all__ = ['SSHAuth', 'SSHClient']
