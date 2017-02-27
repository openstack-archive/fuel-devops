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

import os
import signal
import socket
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
from devops.error import DevopsError
from devops.error import TimeoutError
from devops.helpers.ssh_client import SSHAuth
from devops.helpers.ssh_client import SSHClient
from devops.helpers.subprocess_runner import Subprocess
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
    result = Subprocess.execute(
        "ping -c 1 -W '{timeout:d}' '{host:s}'".format(
            host=host, timeout=timeout))
    return result.exit_code == 0


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


class RunLimit(object):
    def __init__(self, timeout=60, timeout_msg='Timeout'):
        self.seconds = int(timeout)
        self.error_message = timeout_msg
        logger.debug("RunLimit.__init__(timeout={0}, timeout_msg='{1}'"
                     .format(timeout, timeout_msg))

    def handle_timeout(self, signum, frame):
        logger.debug("RunLimit.handle_timeout reached!")
        raise TimeoutError(self.error_message.format(spent=self.seconds))

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, exc_type, value, traceback):
        time_remained = signal.alarm(0)
        logger.debug("RunLimit.__exit__ , remained '{0}' sec"
                     .format(time_remained))


def _check_wait_args(predicate,
                     predicate_args,
                     predicate_kwargs,
                     interval,
                     timeout):

    if not callable(predicate):
        raise TypeError("Not callable raising_predicate has been posted: '{0}'"
                        .format(predicate))
    if not isinstance(predicate_args, (list, tuple)):
        raise TypeError("Incorrect predicate_args type for '{0}', should be "
                        "list or tuple, got '{1}'"
                        .format(predicate, type(predicate_args)))
    if not isinstance(predicate_kwargs, dict):
        raise TypeError("Incorrect predicate_kwargs type, should be dict, "
                        "got {}".format(type(predicate_kwargs)))
    if interval <= 0:
        raise ValueError("For '{0}(*{1}, **{2})', waiting interval '{3}'sec is"
                         " wrong".format(predicate,
                                         predicate_args,
                                         predicate_kwargs,
                                         interval))
    if timeout <= 0:
        raise ValueError("For '{0}(*{1}, **{2})', timeout '{3}'sec is "
                         "wrong".format(predicate,
                                        predicate_args,
                                        predicate_kwargs,
                                        timeout))

def wait(predicate, interval=5, timeout=60, timeout_msg="Waiting timed out",
         predicate_args=None, predicate_kwargs=None):
    """Wait until predicate will become True.

    Options:

    :param interval: - seconds between checks.
    :param timeout:  - raise TimeoutError if predicate won't become True after
                      this amount of seconds.
    :param timeout_msg: - text of the TimeoutError
    :param predicate_args: - positional arguments for given predicate wrapped
                            in list or tuple
    :param predicate_kwargs: - dict with named arguments for the predicate

    """
    predicate_args = predicate_args or []
    predicate_kwargs = predicate_kwargs or {}
    _check_wait_args(predicate, predicate_args, predicate_kwargs,
                     interval, timeout)
    msg = (
        "{msg}\nWaited for pass {cmd}: {spent} seconds."
        "".format(
            msg=timeout_msg,
            cmd=repr(predicate),
            spent="{spent:0.3f}"
        ))

    start_time = time.time()
    with RunLimit(timeout, msg):
        while True:
            result = predicate(*predicate_args, **predicate_kwargs)
            if result:
                logger.debug("wait() completed with result='{0}'"
                             .format(result))
                return result

            if start_time + timeout < time.time():
                err_msg = msg.format(spent=time.time() - start_time)
                logger.error(err_msg)
                raise TimeoutError(err_msg)

            time.sleep(interval)


def wait_pass(raising_predicate, expected=Exception,
              interval=5, timeout=60, timeout_msg="Waiting timed out",
              predicate_args=None, predicate_kwargs=None):
    """Wait for successful return from predicate ignoring expected exception

    Options:

    :param interval: - seconds between checks.
    :param timeout:  - raise TimeoutError if predicate still throwing expected
                       exception after this amount of seconds.
    :param timeout_msg: - text of the TimeoutError
    :param predicate_args: - positional arguments for given predicate wrapped
                            in list or tuple
    :param predicate_kwargs: - dict with named arguments for the predicate
    :param expected_exc: Exception that can be ignored while waiting (its
                         possible to pass several using list/tuple

    """

    predicate_args = predicate_args or []
    predicate_kwargs = predicate_kwargs or {}
    _check_wait_args(raising_predicate, predicate_args, predicate_kwargs,
                     interval, timeout)
    msg = (
        "{msg}\nWaited for pass {cmd}: {spent} seconds."
        "".format(
            msg=timeout_msg,
            cmd=repr(raising_predicate),
            spent="{spent:0.3f}"
        ))

    start_time = time.time()
    with RunLimit(timeout, msg):
        while True:
            try:
                result = raising_predicate(*predicate_args, **predicate_kwargs)
                logger.debug("wait_pass() completed with result='{0}'"
                             .format(result))
                return result
            except expected as e:
                if start_time + timeout < time.time():
                    err_msg = msg.format(spent=time.time() - start_time)
                    logger.error(err_msg)
                    raise TimeoutError(err_msg)

                logger.debug("Got expected exception {!r}, continue".format(e))
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
    return SSHClient(
        ip,
        auth=SSHAuth(
            username=login,
            password=password,
            keys=get_private_keys(env)))


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
             build_images, centos_version=7, static_interface='enp0s3'):
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
    def __init__(self):
        warn(
            'devops.helpers.KeyPolicy is deprecated '
            'and will be removed soon', DeprecationWarning)
        logger.warning(
            'devops.helpers.KeyPolicy is deprecated '
            'and will be removed soon'
        )
        super(KeyPolicy, self).__init__()

    def missing_host_key(self, client, hostname, key):
        return


def ssh(*args, **kwargs):
    warn(
        'devops.helpers.ssh is deprecated '
        'and will be removed soon', DeprecationWarning)
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
