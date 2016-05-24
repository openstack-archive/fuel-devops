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

from __future__ import absolute_import

import logging
import os
import posixpath
import socket
import stat
import time
from warnings import warn

from keystoneauth1.identity import V2Password
from keystoneauth1.session import Session as KeystoneSession
import paramiko
# pylint: disable=import-error
# noinspection PyUnresolvedReferences
from six.moves import http_client
# noinspection PyUnresolvedReferences
from six.moves import xmlrpc_client
# pylint: enable=import-error

from devops.error import AuthenticationError
from devops.error import DevopsCalledProcessError
from devops.error import DevopsError
from devops.error import TimeoutError
from devops.helpers.retry import retry
from devops import logger
from devops.settings import KEYSTONE_CREDS
from devops.settings import SSH_CREDENTIALS
from devops.settings import SSH_SLAVE_CREDENTIALS


def get_free_port():
    for port in range(32000, 32100):
        if not tcp_ping('localhost', port):
            return port
    raise DevopsError('No free ports available')


def icmp_ping(host, timeout=1):
    """Run ICMP ping

    returns True if host is pingable
    False - otherwise.
    """
    return os.system(
        "ping -c 1 -W '%(timeout)d' '%(host)s' 1>/dev/null 2>&1" % {
            'host': host, 'timeout': timeout}) == 0


def tcp_ping_(host, port, timeout=None):
    s = socket.socket()
    if timeout:
        s.settimeout(timeout)
    s.connect((str(host), int(port)))
    s.close()


def _tcp_ping(*args, **kwargs):
    logger.warning('_tcp_ping is deprecated in favor of tcp_ping_')
    warn('_tcp_ping is deprecated in favor of tcp_ping_', DeprecationWarning)
    return tcp_ping_(*args, **kwargs)


def tcp_ping(host, port, timeout=None):
    """Run TCP ping

    returns True if TCP connection to specified host and port
    can be established
    False - otherwise.
    """
    try:
        tcp_ping_(host, port, timeout)
    except socket.error:
        return False
    return True


def wait(predicate, interval=5, timeout=60, timeout_msg="Waiting timed out"):
    """Wait until predicate will become True.

    returns number of seconds that is left or 0 if timeout is None.

    Options:

    interval - seconds between checks.

    timeout  - raise TimeoutError if predicate won't become True after
    this amount of seconds. 'None' disables timeout.

    timeout_msg - text of the TimeoutError

    """
    start_time = time.time()
    if not timeout:
        return predicate()
    while not predicate():
        if start_time + timeout < time.time():
            raise TimeoutError(timeout_msg)

        seconds_to_sleep = max(
            0,
            min(interval, start_time + timeout - time.time()))
        time.sleep(seconds_to_sleep)

    return timeout + start_time - time.time()


def wait_pass(raising_predicate, expected=Exception, interval=5, timeout=None):
    """Wait for successful return from predicate or expected exception"""
    start_time = time.time()
    while True:
        try:
            return raising_predicate()
        except expected:
            if timeout and start_time + timeout < time.time():
                raise
            time.sleep(interval)


def _wait(*args, **kwargs):
    logger.warning('_wait has been deprecated in favor of wait_pass')
    warn('_wait has been deprecated in favor of wait_pass', DeprecationWarning)
    return wait_pass(*args, **kwargs)


def http(host='localhost', port=80, method='GET', url='/', waited_code=200):
    try:
        conn = http_client.HTTPConnection(str(host), int(port))
        conn.request(method, url)
        res = conn.getresponse()

        return res.status == waited_code
    except Exception:
        return False


def get_private_keys(env):
    _ssh_keys = []
    admin_remote = get_admin_remote(env)
    for key_string in ['/root/.ssh/id_rsa',
                       '/root/.ssh/bootstrap.rsa']:
        if admin_remote.isfile(key_string):
            with admin_remote.open(key_string) as f:
                _ssh_keys.append(paramiko.RSAKey.from_private_key(f))
    return _ssh_keys


def get_admin_remote(env, login=SSH_CREDENTIALS['login'],
                     password=SSH_CREDENTIALS['password']):
    admin_ip = get_admin_ip(env)
    wait(lambda: tcp_ping(admin_ip, 22),
         timeout=180,
         timeout_msg=("Admin node {ip} is not accessible by SSH."
                      .format(ip=admin_ip)))
    return env.get_node(
        name='admin').remote(network_name=SSH_CREDENTIALS['admin_network'],
                             login=login,
                             password=password)


def get_node_remote(env, node_name, login=SSH_SLAVE_CREDENTIALS['login'],
                    password=SSH_SLAVE_CREDENTIALS['password']):
    ip = get_slave_ip(env, env.get_node(
        name=node_name).interfaces[0].mac_address)
    wait(lambda: tcp_ping(ip, 22), timeout=180,
         timeout_msg="Node {ip} is not accessible by SSH.".format(ip=ip))
    return SSHClient(ip,
                     username=login,
                     password=password,
                     private_keys=get_private_keys(env))


def get_admin_ip(env):
    return env.get_node(name='admin').get_ip_address_by_network_name('admin')


def get_ip_from_json(js, mac):
    def poor_mac(mac_addr):
        return \
            [m.lower() for m in mac_addr if m.lower() in '01234546789abcdef']

    for node in js:
        for interface in node['meta']['interfaces']:
            if poor_mac(interface['mac']) == poor_mac(mac):
                logger.debug("For mac {0} found ip {1}".format(
                    mac, node['ip']))
                return node['ip']
    raise DevopsError(
        'There is no match between MAC {0} and Nailgun MACs'.format(mac))


def get_slave_ip(env, node_mac_address):
    admin_ip = get_admin_ip(env)
    js = get_nodes(admin_ip)
    return get_ip_from_json(js, node_mac_address)


def get_keys(ip, mask, gw, hostname, nat_interface, dns1, showmenu,
             build_images, centos_version='7', static_interface='enp0s3'):
    if centos_version < 7:
        ip_format = ' ip={ip}'
    else:
        ip_format = ' ip={ip}::{gw}:{mask}:{hostname}:{static_interface}:none'

    return '\n'.join([
        '<Wait>',
        '<Esc>',
        '<Wait>',
        'vmlinuz initrd=initrd.img ks=cdrom:/ks.cfg',
        ip_format,
        ' netmask={mask}'
        ' gw={gw}'
        ' dns1={dns1}',
        ' nameserver={dns1}',
        ' hostname={hostname}',
        ' dhcp_interface={nat_interface}',
        ' showmenu={showmenu}',
        ' build_images={build_images}',
        ' <Enter>',
        ''
    ]).format(
        ip=ip,
        mask=mask,
        gw=gw,
        hostname=hostname,
        nat_interface=nat_interface,
        dns1=dns1,
        showmenu=showmenu,
        build_images=build_images,
        static_interface=static_interface
    )


class KeyPolicy(paramiko.WarningPolicy):
    def missing_host_key(self, client, hostname, key):
        return


class SSHClient(object):
    class get_sudo(object):
        def __init__(self, ssh):
            self.ssh = ssh

        def __enter__(self):
            self.ssh.sudo_mode = True

        def __exit__(self, exc_type, value, traceback):
            self.ssh.sudo_mode = False

    def __init__(self, host, port=22, username=None, password=None,
                 private_keys=None):
        self.host = str(host)
        self.port = int(port)
        self.username = username
        self.password = password
        if not private_keys:
            private_keys = []
        self.private_keys = private_keys

        self.sudo_mode = False
        self.sudo = self.get_sudo(self)
        self._ssh = None
        self.__sftp = None

        self.reconnect()

    @property
    def _sftp(self):
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

    def __exit__(self, *err):
        self.clear()

    @retry(count=3, delay=3)
    def connect(self):
        logging.debug(
            "Connect to '{host}:{port}' as '{user}:{passwd}'".format(
                host=self.host, port=self.port,
                user=self.username, passwd=self.password))
        for private_key in self.private_keys:
            try:
                return self._ssh.connect(
                    self.host, port=self.port, username=self.username,
                    password=self.password, pkey=private_key)
            except paramiko.AuthenticationException:
                continue
        if self.private_keys:
            logging.error("Authentication with keys failed")

        return self._ssh.connect(
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

    def check_call(self, command, verbose=False):
        ret = self.execute(command, verbose)
        if ret['exit_code'] != 0:
            raise DevopsCalledProcessError(command, ret['exit_code'],
                                           ret['stdout'] + ret['stderr'])
        return ret

    def check_stderr(self, command, verbose=False):
        ret = self.check_call(command, verbose)
        if ret['stderr']:
            raise DevopsCalledProcessError(command, ret['exit_code'],
                                           ret['stdout'] + ret['stderr'])
        return ret

    @classmethod
    def execute_together(cls, remotes, command):
        futures = {}
        errors = {}
        for remote in remotes:
            cmd = "%s\n" % command
            if remote.sudo_mode:
                cmd = 'sudo -S bash -c "%s"' % cmd.replace('"', '\\"') \
                                                  .replace('$', '\\$')
            chan = remote._ssh.get_transport().open_session()
            chan.exec_command(cmd)
            futures[remote] = chan
        for remote, chan in futures.items():
            ret = chan.recv_exit_status()
            if ret != 0:
                errors[remote.host] = ret
        if errors:
            raise DevopsCalledProcessError(command, errors)

    def execute(self, command, verbose=False):
        chan, _, stderr, stdout = self.execute_async(command)
        result = {
            'stdout': [],
            'stderr': [],
            'exit_code': 0
        }
        for line in stdout:
            result['stdout'].append(line)
            if verbose:
                logger.info(line)
        for line in stderr:
            result['stderr'].append(line)
            if verbose:
                logger.info(line)
        result['exit_code'] = chan.recv_exit_status()
        chan.close()
        return result

    def execute_async(self, command):
        logging.debug("Executing command: '{}'".format(command.rstrip()))
        chan = self._ssh.get_transport().open_session()
        stdin = chan.makefile('wb')
        stdout = chan.makefile('rb')
        stderr = chan.makefile_stderr('rb')
        cmd = "%s\n" % command
        if self.sudo_mode:
            cmd = 'sudo -S bash -c "%s"' % cmd.replace('"', '\\"') \
                                              .replace('$', '\\$')
            chan.exec_command(cmd)
            if stdout.channel.closed is False:
                stdin.write('%s\n' % self.password)
                stdin.flush()
        else:
            chan.exec_command(cmd)
        return chan, stdin, stderr, stdout

    def mkdir(self, path):
        if self.exists(path):
            return
        logger.debug("Creating directory: %s", path)
        self.execute("mkdir -p %s\n" % path)

    def rm_rf(self, path):
        logger.debug("Removing directory: %s", path)
        self.execute("rm -rf %s" % path)

    def open(self, path, mode='r'):
        return self._sftp.open(path, mode)

    def upload(self, source, target):
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
        try:
            self._sftp.lstat(path)
            return True
        except IOError:
            return False

    def isfile(self, path):
        try:
            attrs = self._sftp.lstat(path)
            return attrs.st_mode & stat.S_IFREG != 0
        except IOError:
            return False

    def isdir(self, path):
        try:
            attrs = self._sftp.lstat(path)
            return attrs.st_mode & stat.S_IFDIR != 0
        except IOError:
            return False


def ssh(*args, **kwargs):
    return SSHClient(*args, **kwargs)


def xmlrpctoken(uri, login, password):
    server = xmlrpc_client.Server(uri)
    try:
        return server.login(login, password)
    except Exception:
        raise AuthenticationError("Error occurred while login process")


def xmlrpcmethod(uri, method):
    server = xmlrpc_client.Server(uri)
    try:
        return getattr(server, method)
    except Exception:
        raise AttributeError("Error occurred while getting server method")


def generate_mac():
    return "64:{0:02x}:{1:02x}:{2:02x}:{3:02x}:{4:02x}".format(
        *bytearray(os.urandom(5)))


def get_file_size(path):
    """Get size of file-like object

    :type path: str
    :rtype : int
    """

    return os.stat(path).st_size


def _get_file_size(*args, **kwargs):
    logger.warning(
        '_get_file_size has been deprecated in favor of get_file_size')
    warn(
        '_get_file_size has been deprecated in favor of get_file_size',
        DeprecationWarning)
    return get_file_size(*args, **kwargs)


def get_nodes(admin_ip):
    keystone_auth = V2Password(
        auth_url="http://{}:5000/v2.0".format(admin_ip),
        username=KEYSTONE_CREDS['username'],
        password=KEYSTONE_CREDS['password'],
        tenant_name=KEYSTONE_CREDS['tenant_name'])
    keystone_session = KeystoneSession(auth=keystone_auth, verify=False)
    nodes = keystone_session.get(
        '/nodes',
        endpoint_filter={'service_type': 'fuel'}
    )
    return nodes.json()
