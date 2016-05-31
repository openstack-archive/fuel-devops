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

import paramiko
# noinspection PyUnresolvedReferences
from six.moves import cStringIO
import six

from devops.error import DevopsCalledProcessError
from devops.helpers.retry import retry
from devops import logger


class SSHClient(object):
    class get_sudo(object):
        """Context manager for call commands with sudo"""
        def __init__(self, ssh):
            self.ssh = ssh

        def __enter__(self):
            self.ssh.sudo_mode = True

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.ssh.sudo_mode = False

    def __init__(self, host, port=22, username=None, password=None,
                 private_keys=None):
        self.host = str(host)
        self.port = int(port)
        self.username = username
        self.__password = password
        if not private_keys:
            private_keys = []
        self.__private_keys = private_keys
        self.__actual_pkey = None

        self.sudo_mode = False
        self.sudo = self.get_sudo(self)
        self._ssh = None
        self.__sftp = None

        self.reconnect()

    @property
    def password(self):
        return self.__password

    @property
    def private_keys(self):
        return self.__private_keys

    @property
    def private_key(self):
        return self.__actual_pkey

    @property
    def public_key(self):
        if self.private_key is None:
            return None
        key = self.private_key
        return '{0} {1}'.format(key.get_name(), key.get_base64())

    @property
    def _sftp(self):
        """SFTP channel access for inheritance

        :raises: paramiko.SSHException
        """
        if self.__sftp is not None:
            return self.__sftp
        logger.warning('SFTP is not connected, try to reconnect')
        self._connect_sftp()
        if self.__sftp is not None:
            return self.__sftp
        raise paramiko.SSHException('SFTP connection failed')

    def clear(self):
        if self.__sftp is not None:
            try:
                self.__sftp.close()
            except Exception:
                logger.exception("Could not close sftp connection")
        try:
            self._ssh.close()
        except Exception:
            logger.exception("Could not close ssh connection")

    def __del__(self):
        self.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.clear()

    @retry(count=3, delay=3)
    def connect(self):
        logger.debug(
            "Connect to '{0}:{1}' as '{2}:{3}'".format(
                self.host, self.port, self.username, self.password))
        for private_key in self.private_keys:
            try:
                self._ssh.connect(
                    self.host, port=self.port, username=self.username,
                    password=self.password, pkey=private_key)
                self.__actual_pkey = private_key
                return
            except paramiko.AuthenticationException:
                continue
        if self.private_keys:
            logger.error("Authentication with keys failed")

        self.__actual_pkey = None
        self._ssh.connect(
            self.host, port=self.port, username=self.username,
            password=self.password)

    def _connect_sftp(self):
        try:
            self.__sftp = self._ssh.open_sftp()
        except paramiko.SSHException:
            logger.warning('SFTP enable failed! SSH only is accessible.')

    def reconnect(self):
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.connect()
        self._connect_sftp()

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
                errors[remote.host] = ret
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

        return result

    @staticmethod
    def _get_str_from_list(src):
        """Join data in list to the string, with python 2&3 compatibility.

        :type src: list
        :rtype: str
        """
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
                stdin.write('%s\n' % self.password)
                stdin.flush()
        else:
            chan.exec_command(cmd)
        return chan, stdin, stderr, stdout

    def execute_through_host(
            self,
            hostname,
            cmd,
            username=None,
            password=None,
            key=None,
            target_port=22):
        if username is None and password is None and key is None:
            username = self.username
            password = self.__password
            key = self.private_key

        intermediate_channel = self._ssh.get_transport().open_channel(
            kind='direct-tcpip',
            dest_addr=(hostname, target_port),
            src_addr=(self.host, 0))
        transport = paramiko.Transport(sock=intermediate_channel)

        # start client and authenticate transport
        transport.connect(username=username, password=password, pkey=key)

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
