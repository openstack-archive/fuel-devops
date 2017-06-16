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
import sys
import threading
import time
import warnings

import paramiko
import six

from devops import error
from devops.helpers import decorators
from devops.helpers import exec_result
from devops.helpers import proc_enums
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
            # noinspection PyTypeChecker
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
        # noinspection PyTypeChecker
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
            except (paramiko.AuthenticationException,
                    paramiko.BadHostKeyException):
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

    def __ne__(self, other):
        return not self.__eq__(other)

    def __deepcopy__(self, memo):
        return self.__class__(
            username=self.username,
            password=self.__password,
            key=self.__key,
            keys=self.__keys.copy()
        )

    def copy(self):
        return self.__class__(
            username=self.username,
            password=self.__password,
            key=self.__key,
            keys=self.__keys
        )

    def __repr__(self):
        _key = (
            None if self.__key is None else
            '<private for pub: {}>'.format(self.public_key)
        )
        _keys = []
        for k in self.__keys:
            if k == self.__key:
                continue
            # noinspection PyTypeChecker
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
        - If exists the same: check for alive, reconnect if required and return
        - If exists with different credentials: delete and continue processing
          create new connection and cache on success
      * Note: each invocation of SSHClient instance will return current dir to
        the root of the current user home dir ("cd ~").
        It is necessary to avoid unpredictable behavior when the same
        connection is used from different places.
        If you need to enter some directory and execute command there, please
        use the following approach:
        cmd1 = "cd <some dir> && <command1>"
        cmd2 = "cd <some dir> && <command2>"

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
                # noinspection PyBroadException
                try:
                    ssh.execute('cd ~', timeout=5)
                except BaseException:  # Note: Do not change to lower level!
                    logger.debug('Reconnect {}'.format(ssh))
                    ssh.reconnect()
                return ssh
            if sys.getrefcount(cls.__cache[key]) == 2:
                # If we have only cache reference and temporary getrefcount
                # reference: close connection before deletion
                logger.debug('Closing {} as unused'.format(cls.__cache[key]))
                cls.__cache[key].close()
            del cls.__cache[key]
        # noinspection PyArgumentList
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
        n_count = 3 if six.PY3 else 4
        # PY3: cache, ssh, temporary
        # PY4: cache, values mapping, ssh, temporary
        for ssh in mcs.__cache.values():
            if sys.getrefcount(ssh) == n_count:
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

    class __get_sudo(object):
        """Context manager for call commands with sudo"""
        def __init__(self, ssh, enforce=None):
            """Context manager for call commands with sudo

            :type ssh: SSHClient
            :type enforce: bool
            """
            self.__ssh = ssh
            self.__sudo_status = ssh.sudo_mode
            self.__enforce = enforce

        def __enter__(self):
            self.__sudo_status = self.__ssh.sudo_mode
            if self.__enforce is not None:
                self.__ssh.sudo_mode = self.__enforce

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.__ssh.sudo_mode = self.__sudo_status

    # noinspection PyPep8Naming
    class get_sudo(__get_sudo):
        """Context manager for call commands with sudo"""

        def __init__(self, ssh, enforce=True):
            warnings.warn(
                'SSHClient.get_sudo(SSHClient()) is deprecated in favor of '
                'SSHClient().sudo(enforce=...) , which is much more powerful.')
            super(self.__class__, self).__init__(ssh=ssh, enforce=enforce)

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
        self.__lock = threading.RLock()

        self.__hostname = host
        self.__port = port

        self.sudo_mode = False
        self.__ssh = paramiko.SSHClient()
        self.__ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.__sftp = None

        self.__auth = auth if auth is None else auth.copy()

        if auth is None:
            msg = (
                'SSHClient(host={host}, port={port}, username={username}): '
                'initialization by username/password/private_keys '
                'is deprecated in favor of SSHAuth usage. '
                'Please update your code'.format(
                    host=host, port=port, username=username
                ))
            warnings.warn(msg, DeprecationWarning)
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
        """Connection lock

        :rtype: threading.RLock
        """
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
        warnings.warn(
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

    @decorators.retry(paramiko.SSHException, count=3, delay=3)
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

        :rtype: paramiko.sftp_client.SFTPClient
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
            # noinspection PyBroadException
            try:
                self.__ssh.close()
                self.__sftp = None
            except Exception:
                logger.exception("Could not close ssh connection")
                if self.__sftp is not None:
                    # noinspection PyBroadException
                    try:
                        self.__sftp.close()
                    except Exception:
                        logger.exception("Could not close sftp connection")

    @staticmethod
    def clear():
        warnings.warn(
            "clear is removed: use close() only if it mandatory: "
            "it's automatically called on revert|shutdown|suspend|destroy",
            DeprecationWarning
        )

    @classmethod
    def _clear_cache(cls):
        """Enforce clear memorized records"""
        warnings.warn(
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

    def sudo(self, enforce=None):
        """Call contextmanager for sudo mode change

        :type enforce: bool
        :param enforce: Enforce sudo enabled or disabled. By default: None
        """
        return self.__get_sudo(ssh=self, enforce=enforce)

    def check_call(
            self,
            command, verbose=False, timeout=None,
            error_info=None,
            expected=None, raise_on_err=True, **kwargs):
        """Execute command and check for return code

        :type command: str
        :type verbose: bool
        :type timeout: int
        :type error_info: str
        :type expected: list
        :type raise_on_err: bool
        :rtype: ExecResult
        :raises: DevopsCalledProcessError
        """
        if expected is None:
            expected = [proc_enums.ExitCodes.EX_OK]
        else:
            expected = [
                proc_enums.ExitCodes(code)
                if (
                    isinstance(code, int) and
                    code in proc_enums.ExitCodes.__members__.values())
                else code
                for code in expected
                ]
        ret = self.execute(command, verbose, timeout, **kwargs)
        if ret['exit_code'] not in expected:
            message = (
                "{append}Command '{cmd!r}' returned exit code {code!s} while "
                "expected {expected!s}\n".format(
                    append=error_info + '\n' if error_info else '',
                    cmd=command,
                    code=ret['exit_code'],
                    expected=expected,
                ))
            logger.error(message)
            if raise_on_err:
                raise error.DevopsCalledProcessError(
                    command, ret['exit_code'],
                    expected=expected,
                    stdout=ret['stdout_brief'],
                    stderr=ret['stdout_brief'])
        return ret

    def check_stderr(
            self,
            command, verbose=False, timeout=None,
            error_info=None,
            raise_on_err=True, **kwargs):
        """Execute command expecting return code 0 and empty STDERR

        :type command: str
        :type verbose: bool
        :type timeout: int
        :type error_info: str
        :type raise_on_err: bool
        :rtype: ExecResult
        :raises: DevopsCalledProcessError
        """
        ret = self.check_call(
            command, verbose, timeout=timeout,
            error_info=error_info, raise_on_err=raise_on_err, **kwargs)
        if ret['stderr']:
            message = (
                "{append}Command '{cmd!r}' STDERR while not expected\n"
                "\texit code: {code!s}\n".format(
                    append=error_info + '\n' if error_info else '',
                    cmd=command,
                    code=ret['exit_code'],
                ))
            logger.error(message)
            if raise_on_err:
                raise error.DevopsCalledProcessError(
                    command,
                    ret['exit_code'],
                    stdout=ret['stdout_brief'],
                    stderr=ret['stdout_brief'])
        return ret

    @classmethod
    def execute_together(
            cls, remotes, command, expected=None, raise_on_err=True, **kwargs):
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
            chan, _, _, _ = remote.execute_async(command, **kwargs)
            futures[remote] = chan
        for remote, chan in futures.items():
            ret = chan.recv_exit_status()
            chan.close()
            if ret not in expected:
                errors[remote.hostname] = ret
        if errors and raise_on_err:
            raise error.DevopsCalledProcessError(command, errors)

    @classmethod
    def __exec_command(
            cls, command, channel, stdout, stderr, timeout, verbose=False):
        """Get exit status from channel with timeout

        :type command: str
        :type channel: paramiko.channel.Channel
        :type stdout: paramiko.channel.ChannelFile
        :type stderr: paramiko.channel.ChannelFile
        :type timeout: int
        :type verbose: bool
        :rtype: ExecResult
        :raises: TimeoutError
        """
        def poll_stream(src, verb_logger=None):
            dst = []
            try:
                for line in src:
                    dst.append(line)
                    if verb_logger is not None:
                        verb_logger(
                            line.decode('utf-8',
                                        errors='backslashreplace').rstrip()
                        )
            except IOError:
                pass
            return dst

        def poll_streams(result, channel, stdout, stderr, verbose):
            if channel.recv_ready():
                result.stdout += poll_stream(
                    src=stdout,
                    verb_logger=logger.info if verbose else logger.debug)
            if channel.recv_stderr_ready():
                result.stderr += poll_stream(
                    src=stderr,
                    verb_logger=logger.error if verbose else logger.debug)

        @decorators.threaded(started=True)
        def poll_pipes(stdout, stderr, result, stop, channel):
            """Polling task for FIFO buffers

            :type stdout: paramiko.channel.ChannelFile
            :type stderr: paramiko.channel.ChannelFile
            :type result: ExecResult
            :type stop: Event
            :type channel: paramiko.channel.Channel
            """

            while not stop.isSet():
                time.sleep(0.1)
                poll_streams(
                    result=result,
                    channel=channel,
                    stdout=stdout,
                    stderr=stderr,
                    verbose=verbose
                )

                if channel.status_event.is_set():
                    result.exit_code = result.exit_code = channel.exit_status

                    result.stdout += poll_stream(
                        src=stdout,
                        verb_logger=logger.info if verbose else logger.debug)
                    result.stderr += poll_stream(
                        src=stderr,
                        verb_logger=logger.error if verbose else logger.debug)

                    stop.set()

        # channel.status_event.wait(timeout)
        result = exec_result.ExecResult(cmd=command)
        stop_event = threading.Event()
        message = "\n".join(
            "\nExecuting command: {!r}".format(command.rstrip()).split("\\n"))
        if verbose:
            logger.info(message)
        else:
            logger.debug(message)

        poll_pipes(
            stdout=stdout,
            stderr=stderr,
            result=result,
            stop=stop_event,
            channel=channel
        )

        stop_event.wait(timeout)

        # Process closed?
        if stop_event.isSet():
            stop_event.clear()
            channel.close()
            return result

        stop_event.set()
        channel.close()

        wait_err_msg = ('Wait for {0!r} during {1}s: no return code!\n'
                        .format(command, timeout))
        output_brief_msg = ('\tSTDOUT:\n'
                            '{0}\n'
                            '\tSTDERR"\n'
                            '{1}'.format(result.stdout_brief,
                                         result.stderr_brief))
        logger.debug(wait_err_msg)
        raise error.TimeoutError(wait_err_msg + output_brief_msg)

    def execute(self, command, verbose=False, timeout=None, **kwargs):
        """Execute command and wait for return code

        :type command: str
        :type verbose: bool
        :type timeout: int
        :rtype: ExecResult
        :raises: TimeoutError
        """
        chan, _, stderr, stdout = self.execute_async(command, **kwargs)

        result = self.__exec_command(
            command, chan, stdout, stderr, timeout,
            verbose=verbose
        )

        message = (
            '\n{cmd!r} execution results: Exit code: {code!s}'.format(
                cmd=command,
                code=result.exit_code
            ))
        if verbose:
            logger.info(message)
        else:
            logger.debug(message)
        return result

    def execute_async(self, command, get_pty=False):
        """Execute command in async mode and return channel with IO objects

        :type command: str
        :type get_pty: bool
        :rtype:
            tuple(
                paramiko.Channel,
                paramiko.ChannelFile,
                paramiko.ChannelFile,
                paramiko.ChannelFile
            )
        """
        message = "\n".join(
            "\nExecuting command: {!r}".format(command.rstrip()).split("\\n"))
        logger.debug(message)

        chan = self._ssh.get_transport().open_session()

        if get_pty:
            # Open PTY
            chan.get_pty(
                term='vt100',
                width=80, height=24,
                width_pixels=0, height_pixels=0
            )

        stdin = chan.makefile('wb')
        stdout = chan.makefile('rb')
        stderr = chan.makefile_stderr('rb')
        cmd = "{}\n".format(command)
        if self.sudo_mode:
            encoded_cmd = base64.b64encode(cmd.encode('utf-8')).decode('utf-8')
            cmd = ("sudo -S bash -c 'eval \"$(base64 -d "
                   "<(echo \"{0}\"))\"'").format(
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
            target_port=22,
            timeout=None,
            verbose=False
    ):
        """Execute command on remote host through currently connected host

        :type hostname: str
        :type cmd: str
        :type auth: SSHAuth
        :type target_port: int
        :type timeout: int
        :type verbose: bool
        :rtype: ExecResult
        :raises: TimeoutError
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

        # noinspection PyDictCreation
        result = self.__exec_command(
            cmd, channel, stdout, stderr, timeout, verbose=verbose)

        intermediate_channel.close()

        return result

    def mkdir(self, path):
        """run 'mkdir -p path' on remote

        :type path: str
        """
        if self.exists(path):
            return
        logger.debug("Creating directory: {}".format(path))
        # noinspection PyTypeChecker
        self.execute("mkdir -p {}\n".format(path))

    def rm_rf(self, path):
        """run 'rm -rf path' on remote

        :type path: str
        """
        logger.debug("rm -rf {}".format(path))
        # noinspection PyTypeChecker
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

    def stat(self, path):
        """Get stat info for path with following symlinks

        :type path: str
        :rtype: paramiko.sftp_attr.SFTPAttributes
        """
        return self._sftp.stat(path)

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
