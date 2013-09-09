import os
import urllib
import stat
import socket
import time
import httplib
import xmlrpclib
import random
from threading import Thread
import BaseHTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
import posixpath
import logging

import paramiko

from devops.helpers.retry import retry
from devops.error import DevopsError, DevopsCalledProcessError, TimeoutError, \
    AuthenticationError


logger = logging.getLogger(__name__)


def get_free_port():
    ports = range(32000, 32100)
    random.shuffle(ports)
    for port in ports:
        if not tcp_ping('localhost', port):
            return port
    raise DevopsError("No free ports available")


def icmp_ping(host, timeout=1):
    """
    icmp_ping(host, timeout=1) - returns True if host is pingable; False - otherwise.
    """
    return os.system(
        "ping -c 1 -W '%(timeout)d' '%(host)s' 1>/dev/null 2>&1" % {
            'host': str(host), 'timeout': timeout}) == 0


def _tcp_ping(host, port):
    s = socket.socket()
    s.connect((str(host), int(port)))
    s.close()


def tcp_ping(host, port):
    """
    tcp_ping(host, port) - returns True if TCP connection to specified host and port can be established; False - otherwise.
    """
    try:
        _tcp_ping(host, port)
    except socket.error:
        return False
    return True


def wait(predicate, interval=5, timeout=None):
    """
    wait(predicate, interval=5, timeout=None) - wait until predicate will 
    become True. Returns number of seconds that is left or 0 if timeout is None.

    Options:

    interval - seconds between checks.

    timeout  - raise TimeoutError if predicate won't become True after 
    this amount of seconds. 'None' disables timeout.
    """
    start_time = time.time()
    while not predicate():
        if timeout and start_time + timeout < time.time():
            raise TimeoutError("Waiting timed out")

        seconds_to_sleep = interval
        if timeout:
            seconds_to_sleep = max(
                0,
                min(seconds_to_sleep, start_time + timeout - time.time()))
        time.sleep(seconds_to_sleep)

    return timeout + start_time - time.time() if timeout else 0


def _wait(raising_predicate, expected=Exception, interval=5, timeout=None):
    start_time = time.time()
    while True:
        try:
            return raising_predicate()
        except expected:
            if timeout and start_time + timeout < time.time():
                raise
            time.sleep(interval)


def http(host='localhost', port=80, method='GET', url='/', waited_code=200):
    try:
        conn = httplib.HTTPConnection(str(host), int(port))
        conn.request(method, url)
        res = conn.getresponse()

        if res.status == waited_code:
            return True
        return False
    except:
        return False


class KeyPolicy(paramiko.WarningPolicy):
    def missing_host_key(self, client, hostname, key):
        return


class SSHClient(object):
    class get_sudo(object):
        def __init__(self, ssh):
            self.ssh = ssh

        def __enter__(self):
            self.ssh.sudo_mode = True

        def __exit__(self, type, value, traceback):
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

        self.reconnect()

    def __del__(self):
        self._sftp.close()
        self._ssh.close()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass

    @retry(count=3, delay=3)
    def connect(self):
        logging.debug(
            "Connect to '%s:%s' as '%s:%s'" % (
                self.host, self.port, self.username, self.password))
        for private_key in self.private_keys:
            try:
                return self._ssh.connect(
                    self.host, port=self.port, username=self.username,
                    password=self.password, pkey=private_key)
            except paramiko.AuthenticationException:
                pass
        return self._ssh.connect(
            self.host, port=self.port, username=self.username,
            password=self.password)

    def reconnect(self):
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.connect()
        self._sftp = self._ssh.open_sftp()

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
                cmd = 'sudo -S bash -c "%s"' % cmd.replace('"', '\\"')
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
        chan, stdin, stderr, stdout = self.execute_async(command)
        result = {
            'stdout': [],
            'stderr': [],
            'exit_code': 0
        }
        for line in stdout:
            result['stdout'].append(line)
            if verbose:
                print line
        for line in stderr:
            result['stderr'].append(line)
            if verbose:
                print line
        result['exit_code'] = chan.recv_exit_status()
        chan.close()
        return result

    def execute_async(self, command):
        logging.debug("Executing command: '%s'" % command.rstrip())
        chan = self._ssh.get_transport().open_session()
        stdin = chan.makefile('wb')
        stdout = chan.makefile('rb')
        stderr = chan.makefile_stderr('rb')
        cmd = "%s\n" % command
        if self.sudo_mode:
            cmd = 'sudo -S bash -c "%s"' % cmd.replace('"', '\\"')
        chan.exec_command(cmd)
        if stdout.channel.closed is False:
            stdin.write('%s\n' % self.password)
            stdin.flush()
        return chan, stdin, stderr, stdout

    def mkdir(self, path):
        if self.exists(path):
            return
        logger.debug("Creating directory: %s" % path)
        self.execute("mkdir -p %s\n" % path)

    def rm_rf(self, path):
        logger.debug("Removing directory: %s" % path)
        self.execute("rm -rf %s" % path)

    def open(self, path, mode='r'):
        return self._sftp.open(path, mode)

    def upload(self, source, target):
        logger.debug("Copying '%s' -> '%s'" % (source, target))

        if self.isdir(target):
            target = posixpath.join(target, os.path.basename(source))

        if not os.path.isdir(source):
            self._sftp.put(source, target)
            return

        for rootdir, subdirs, files in os.walk(source):
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


class HttpServer:
    class Handler(SimpleHTTPRequestHandler):
        logger = logging.getLogger('devops.helpers.http_server')

        def __init__(self, docroot, *args, **kwargs):
            self.docroot = docroot
            SimpleHTTPRequestHandler.__init__(self, *args, **kwargs)

        # Suppress reverse DNS lookups to speed up processing
        def address_string(self):
            return self.client_address[0]

        # Handle docroot
        def translate_path(self, path):
            """Translate a /-separated PATH to the local filename syntax.

            Components that mean special things to the local file system
            (e.g. drive or directory names) are ignored.  (XXX They should
            probably be diagnosed.)

            """
            # abandon query parameters
            path = path.split('?', 1)[0]
            path = path.split('#', 1)[0]
            path = posixpath.normpath(urllib.unquote(path))
            words = path.split('/')
            words = filter(None, words)
            path = self.docroot
            for word in words:
                drive, word = os.path.splitdrive(word)
                head, word = os.path.split(word)
                path = os.path.join(path, word)
            return path

        def log_message(self, format, *args):
            self.logger.info(format % args)

    def __init__(self, document_root):
        self.port = get_free_port()
        self.document_root = document_root

        def handler_factory(*args, **kwargs):
            return HttpServer.Handler(document_root, *args, **kwargs)

        self._server = BaseHTTPServer.HTTPServer(
            ('', self.port),
            handler_factory)
        self._thread = Thread(target=self._server.serve_forever)
        self._thread.daemon = True

    def start(self):
        self._thread.start()

    def run(self):
        self._thread.join()

    def stop(self):
        self._server.shutdown()
        self._thread.join()


def http_server(document_root):
    server = HttpServer(document_root)
    server.start()
    return server


def xmlrpctoken(uri, login, password):
    server = xmlrpclib.Server(uri)
    try:
        return server.login(login, password)
    except:
        raise AuthenticationError("Error occured while login process")


def xmlrpcmethod(uri, method):
    server = xmlrpclib.Server(uri)
    try:
        return getattr(server, method)
    except:
        raise AttributeError("Error occured while getting server method")


def generate_mac():
    return "64:{0:02x}:{1:02x}:{2:02x}:{3:02x}:{4:02x}".format(
        *bytearray(os.urandom(5)))


def _get_file_size(path):
    """
    :type file: String
    :rtype : int
    """
    with open(path) as file:
        current = file.tell()
        try:
            file.seek(0, 2)
            size = file.tell()
        finally:
            file.seek(current)
        return size
