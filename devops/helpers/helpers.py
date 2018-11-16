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

import functools
import os
import signal
import socket
import string
import time
import warnings
# noinspection PyPep8Naming
import xml.etree.ElementTree as ET

from dateutil import tz
import exec_helpers
import six
# pylint: disable=import-error
# noinspection PyUnresolvedReferences
from six.moves import http_client
# noinspection PyUnresolvedReferences
from six.moves import xmlrpc_client
# pylint: enable=import-error

from devops import error
from devops import logger
from devops import settings


def get_free_port():
    for port in range(32000, 32100):
        if not tcp_ping('localhost', port):
            return port
    raise error.DevopsError('No free ports available')


def icmp_ping(host, timeout=1):
    """Run ICMP ping

    returns True if host is pingable
    False - otherwise.
    """
    result = exec_helpers.Subprocess().execute(
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


class RunLimit(object):
    def __init__(self, timeout=60, timeout_msg='Timeout'):
        self.seconds = int(timeout)
        self.error_message = timeout_msg
        logger.debug("RunLimit.__init__(timeout={0}, timeout_msg='{1}'"
                     .format(timeout, timeout_msg))

    def handle_timeout(self, signum, frame):
        logger.debug("RunLimit.handle_timeout reached!")
        raise error.TimeoutError(self.error_message.format(spent=self.seconds))

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)
        logger.debug("RunLimit.__enter__(seconds={0}".format(self.seconds))

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
                raise error.TimeoutError(err_msg)

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
                    raise error.TimeoutError(err_msg)

                logger.debug("Got expected exception {!r}, continue".format(e))
                time.sleep(interval)


def wait_tcp(host, port, timeout, timeout_msg="Waiting timed out"):
    wait(tcp_ping, timeout=timeout, timeout_msg=timeout_msg,
         predicate_kwargs={'host': host, 'port': port})


def wait_ssh_cmd(
        host,
        port,
        check_cmd,
        username=settings.SSH_CREDENTIALS['login'],
        password=settings.SSH_CREDENTIALS['password'],
        timeout=0):
    ssh = exec_helpers.SSHClient(host=host, port=port,
                                 auth=exec_helpers.SSHAuth(
                                     username=username,
                                     password=password))
    wait(lambda: not ssh.execute(check_cmd)['exit_code'],
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
    msg = (
        'get_private_keys has been deprecated in favor of '
        'DevopsEnvironment.get_private_keys')
    logger.warning(msg)
    warnings.warn(msg, DeprecationWarning)

    from devops import client
    denv = client.DevopsClient().get_env(env.name)
    return denv.get_private_keys()


def get_admin_remote(
        env,
        login=settings.SSH_CREDENTIALS['login'],
        password=settings.SSH_CREDENTIALS['password']):
    msg = (
        'get_admin_remote has been deprecated in favor of '
        'DevopsEnvironment.get_admin_remote')
    logger.warning(msg)
    warnings.warn(msg, DeprecationWarning)

    from devops import client
    denv = client.DevopsClient().get_env(env.name)
    return denv.get_admin_remote(login=login, password=password)


def get_node_remote(
        env,
        node_name,
        login=settings.SSH_SLAVE_CREDENTIALS['login'],
        password=settings.SSH_SLAVE_CREDENTIALS['password']):
    msg = (
        'get_node_remote has been deprecated in favor of '
        'DevopsEnvironment.get_node_remote')
    logger.warning(msg)
    warnings.warn(msg, DeprecationWarning)

    from devops.client import DevopsClient
    denv = DevopsClient().get_env(env.name)
    return denv.get_node_remote(
        node_name=node_name, login=login, password=password)


def get_admin_ip(env):
    msg = (
        'get_admin_ip has been deprecated in favor of '
        'DevopsEnvironment.get_admin_ip')
    logger.warning(msg)
    warnings.warn(msg, DeprecationWarning)

    from devops import client
    denv = client.DevopsClient().get_env(env.name)
    return denv.get_admin_ip()


def get_slave_ip(env, node_mac_address):
    msg = (
        'get_slave_ip has been deprecated in favor of '
        'DevopsEnvironment.get_node_ip')
    logger.warning(msg)
    warnings.warn(msg, DeprecationWarning)

    from devops import client
    from devops.client import nailgun
    denv = client.DevopsClient().get_env(env.name)
    ng_client = nailgun.NailgunClient(ip=denv.get_admin_ip())
    return ng_client.get_slave_ip_by_mac(node_mac_address)


def xmlrpctoken(uri, login, password):
    server = xmlrpc_client.Server(uri)
    try:
        return server.login(login, password)
    except Exception:
        raise error.AuthenticationError("Error occurred while login process")


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
        return functools.reduce(getattr, attr.split(splitter), obj)
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
    msg = ('get_nodes has been deprecated in favor of '
           'NailgunClient.get_nodes_json')
    logger.warning(msg)
    warnings.warn(msg, DeprecationWarning)

    from devops.client import nailgun
    ng_client = nailgun.NailgunClient(ip=admin_ip)
    return ng_client.get_nodes_json()


def utc_to_local(t):
    """Converts UTC datetime to local

    :type t: datetime.datetime
    :rtype : datetime.datetime
    """
    # set utc tzinfo
    t = t.replace(tzinfo=tz.tzutc())
    # convert to local timezone
    return t.astimezone(tz.tzlocal())


def format_data(data_content, data_context):
    """Dict wrapper.

    Dict wrapper that returns key name
    in case of key missing in the dictionary
    """

    class temp_dict(dict):
        def __init__(self, kw):
            self.__dict = kw

        def __getitem__(self, key):
            return self.__dict.get(key, '{' + str(key) + '}')

    return string.Formatter().vformat(data_content, [], temp_dict(
        data_context))
