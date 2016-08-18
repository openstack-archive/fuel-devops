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

from functools import partial
# pylint: disable=redefined-builtin
from functools import reduce
# pylint: enable=redefined-builtin
import os
import socket
import time
import xml.etree.ElementTree as ET

from dateutil import tz
from keystoneauth1.identity import V2Password
from keystoneauth1.session import Session as KeystoneSession
import paramiko
import six
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
            msg = (
                "{msg}\nWaited for pass {cmd}: {spent:0.3f} seconds."
                "".format(
                    msg=timeout_msg,
                    cmd=predicate.func_name,
                    spent=time.time() - start_time
                ))
            logger.debug(msg)
            raise TimeoutError(timeout_msg)

        seconds_to_sleep = max(
            0,
            min(interval, start_time + timeout - time.time()))
        time.sleep(seconds_to_sleep)

    return timeout + start_time - time.time()


def wait_pass(
        raising_predicate,
        expected=Exception,
        interval=5, timeout=None,
        timeout_msg="Waiting timed out"
):
    """Wait for successful return from predicate or expected exception"""
    if not callable(raising_predicate):
        raise TypeError('Not callable raising_predicate has been posted')
    start_time = time.time()
    while True:
        try:
            return raising_predicate()
        except expected:
            if timeout and start_time + timeout < time.time():
                msg = (
                    "{msg}\nWaited for pass {cmd}: {spent:0.3f} seconds."
                    "".format(
                        msg=timeout_msg,
                        cmd=raising_predicate.func_name,
                        spent=time.time() - start_time
                    ))
                logger.error(msg)
                raise
            time.sleep(interval)


def wait_tcp(host, port, timeout, timeout_msg="Waiting timed out"):
    is_port_active = partial(tcp_ping, host=host, port=port)
    wait(is_port_active, timeout=timeout, timeout_msg=timeout_msg)


def wait_ssh_cmd(
        host,
        port,
        check_cmd,
        username=SSH_CREDENTIALS['login'],
        password=SSH_CREDENTIALS['password'],
        timeout=0):
    ssh_client = SSHClient(host=host, port=port,
                           auth=SSHAuth(
                               username=username,
                               password=password))
    wait(lambda: not ssh_client.execute(check_cmd)['exit_code'],
         timeout=timeout)


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


def xml_tostring(tree):
    """Converts ElementTree object to string

    :type tree: ElementTree
    :rtype: str
    """
    if six.PY2:
        return ET.tostring(tree)
    else:
        return ET.tostring(tree, encoding='unicode')


def deepgetattr(obj, attr, default=None, splitter='.', do_raise=False):
    """Recurses through an attribute chain to get the ultimate value.

    :type obj: object
    :param obj: object instance to get attribute from
    :type attr: str
    :param attr: attributes joined by some symbol. e.g. 'a.b.c.d'
    :type default: any
    :param default: default value (returned only in case of
                    AttributeError)
    :type splitter: str
    :param splitter: one or more symbols to be used to split attr
                     parameter
    :type do_raise: bool
    :param do_raise: if True then instead of returning default value
                     AttributeError will be raised

    """
    try:
        return reduce(getattr, attr.split(splitter), obj)
    except AttributeError:
        if do_raise:
            raise
        return default


def underscored(*args):
    """Joins multiple strings using uderscore symbol.

       Skips empty strings.
    """
    return '_'.join(filter(bool, list(args)))


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


def utc_to_local(t):
    """Converts UTC datetime to local

    :type t: datetime.datetime
    :rtype : datetime.datetime
    """
    # set utc tzinfo
    t = t.replace(tzinfo=tz.tzutc())
    # convert to local timezone
    return t.astimezone(tz.tzlocal())
