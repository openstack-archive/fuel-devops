#    Copyright 2015 Mirantis, Inc.
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

import abc
import time

from six import add_metaclass

from devops.error import TimeoutError
from devops.helpers.helpers import get_admin_ip
from devops.helpers.helpers import get_admin_remote
from devops.helpers.helpers import get_node_remote
from devops.helpers.helpers import wait
from devops.helpers.retry import retry
from devops import logger


@retry(count=3, delay=60)
def sync_time(env, node_names, skip_sync=False):
    """Synchronize time on nodes

       param: env - environment object
       param: node_names - list of devops node names
       param: skip_sync - only get the current time without sync
       return: dict{node_name: node_time, ...}
    """
    with GroupNtpSync(env, node_names) as g_ntp:

        if not skip_sync:
            if g_ntp.admin_ntps:
                g_ntp.do_sync_time(g_ntp.admin_ntps)

            if g_ntp.pacemaker_ntps:
                g_ntp.do_sync_time(g_ntp.pacemaker_ntps)

            if g_ntp.other_ntps:
                g_ntp.do_sync_time(g_ntp.other_ntps)

        all_ntps = g_ntp.admin_ntps + g_ntp.pacemaker_ntps + g_ntp.other_ntps
        results = {ntp.node_name: ntp.date[0].rstrip() for ntp in all_ntps}

    return results


@add_metaclass(abc.ABCMeta)
class AbstractNtp(object):
    @abc.abstractmethod
    def start(self):
        """Start ntp daemon"""

    @abc.abstractmethod
    def stop(self):
        """Stop ntp daemon"""

    @abc.abstractmethod
    def get_peers(self):
        """Get connected clients"""

    @abc.abstractmethod
    def set_actual_time(self, timeout=600):
        pass

    @abc.abstractmethod
    def wait_peer(self, interval=8, timeout=600):
        """Wait for connection"""

    @abc.abstractproperty
    def date(self):
        """get date command output"""

    @abc.abstractproperty
    def remote(self):
        """remote object"""

    @abc.abstractproperty
    def admin_ip(self):
        """admin node ip"""

    is_connected = abc.abstractproperty(
        fget=lambda: None, fset=lambda status: None, doc="connectivity status")

    is_synchronized = abc.abstractproperty(
        fget=lambda: None, fset=lambda status: None, doc="sync status")

    @abc.abstractproperty
    def node_name(self):
        """node name"""

    @abc.abstractproperty
    def peers(self):
        """peers"""

    @abc.abstractproperty
    def is_pacemaker(self):
        """how NTPD is managed - by init script or by pacemaker"""

    @abc.abstractproperty
    def server(self):
        """IP of a server from which the time will be synchronized."""


# pylint: disable=abstract-method
# noinspection PyAbstractClass
class BaseNtp(AbstractNtp):
    def __init__(self, remote, node_name='node', admin_ip=None):
        self.__remote = remote
        self.__node_name = node_name
        self.__admin_ip = admin_ip
        self.__is_synchronized = False
        self.__is_connected = False
        # Get IP of a server from which the time will be synchronized.
        cmd = "awk '/^server/ && $2 !~ /127.*/ {print $2}' /etc/ntp.conf"
        self.__server = remote.execute(cmd)['stdout'][0]

    @property
    def server(self):
        return self.__server

    @property
    def remote(self):
        return self.__remote

    @property
    def is_connected(self):
        return self.__is_connected

    @is_connected.setter
    def is_connected(self, status):
        self.__is_connected = status

    @property
    def is_synchronized(self):
        return self.__is_synchronized

    @is_synchronized.setter
    def is_synchronized(self, status):
        self.__is_synchronized = status

    @property
    def node_name(self):
        return self.__node_name

    @property
    def admin_ip(self):
        return self.__admin_ip

    @property
    def peers(self):
        return self.get_peers()[2:]

    @property
    def date(self):
        return self.remote.execute("date")['stdout']

    def set_actual_time(self, timeout=600):
        # Waiting for parent server until it starts providing the time
        cmd = "ntpdate -p 4 -t 0.2 -bu {0}".format(self.server)
        self.is_synchronized = False
        try:
            wait(lambda: not self.remote.execute(cmd)['exit_code'], timeout)
            self.remote.execute('hwclock -w')
            self.is_synchronized = True
        except TimeoutError as e:
            logger.debug('Time sync failed with {}'.format(e))

        return self.is_synchronized

    def wait_peer(self, interval=8, timeout=600):
        self.is_connected = False

        start_time = time.time()
        while start_time + timeout > time.time():
            # peer = `ntpq -pn 127.0.0.1`
            logger.debug(
                "Node: {0}, ntpd peers: {1}".format(self.node_name, self.peers)
            )

            for peer in self.peers:
                p = peer.split()
                remote = str(p[0])
                reach = int(p[6], 8)  # From octal to int
                offset = float(p[8])
                jitter = float(p[9])

                # 1. offset and jitter should not be higher than 500
                # Otherwise, time should be re-set.
                if (abs(offset) > 500) or (abs(jitter) > 500):
                    return self.is_connected

                # 2. remote should be marked with tally  '*'
                if remote[0] != '*':
                    continue

                # 3. reachability bit array should have '1' at least in
                # two lower bits as the last two successful checks
                if reach & 3 == 3:
                    self.is_connected = True
                    return self.is_connected

            time.sleep(interval)
        return self.is_connected
# pylint: enable=abstract-method


class NtpInitscript(BaseNtp):
    """NtpInitscript."""  # TODO(ddmitriev) documentation
    def __init__(self, remote, node_name='node', admin_ip=None):

        super(NtpInitscript, self).__init__(
            remote, node_name, admin_ip)
        cmd = "find /etc/init.d/ -regex '/etc/init.d/ntp.?'"
        self.__service = remote.execute(cmd)['stdout'][0].strip()

    def start(self):
        self.is_connected = False
        self.remote.execute("{0} start".format(self.__service))

    def stop(self):
        self.is_connected = False
        self.remote.execute("{0} stop".format(self.__service))

    def get_peers(self):
        return self.remote.execute('ntpq -pn 127.0.0.1')['stdout']

    @property
    def is_pacemaker(self):
        return False

    def __repr__(self):
        return "{0}(remote={1}, node_name={2}, admin_ip={3})".format(
            self.__class__.__name__, self.remote, self.node_name, self.admin_ip
        )


class NtpPacemaker(BaseNtp):
    """NtpPacemaker."""  # TODO(ddmitriev) documentation

    def start(self):
        self.is_connected = False

        # Temporary workaround of the LP bug #1441121
        self.remote.execute('ip netns exec vrouter ip l set dev lo up')

        self.remote.execute('crm resource start p_ntp')

    def stop(self):
        self.is_connected = False
        self.remote.execute('crm resource stop p_ntp; killall ntpd')

    def get_peers(self):
        return self.remote.execute(
            'ip netns exec vrouter ntpq -pn 127.0.0.1')['stdout']

    @property
    def is_pacemaker(self):
        return True

    def __repr__(self):
        return "{0}(remote={1}, node_name={2}, admin_ip={3})".format(
            self.__class__.__name__, self.remote, self.node_name, self.admin_ip
        )


class NtpSystemd(BaseNtp):
    """NtpSystemd."""  # TODO(ddmitriev) documentation

    def start(self):
        self.is_connected = False
        self.remote.execute('systemctl start ntpd')

    def stop(self):
        self.is_connected = False
        self.remote.execute('systemctl stop ntpd')

    def get_peers(self):
        return self.remote.execute('ntpq -pn 127.0.0.1')['stdout']

    @property
    def is_pacemaker(self):
        return False

    def __repr__(self):
        return "{0}(remote={1}, node_name={2}, admin_ip={3})".format(
            self.__class__.__name__, self.remote, self.node_name, self.admin_ip
        )


class GroupNtpSync(object):
    """Synchronize a group of nodes."""
    @staticmethod
    def get_ntp(remote, node_name='node', admin_ip=None):
        # Detect how NTPD is managed - by init script or by pacemaker.
        pcs_cmd = "ps -C pacemakerd && crm_resource --resource p_ntp --locate"
        systemd_cmd = "systemctl list-unit-files| grep ntpd"

        # pylint: disable=redefined-variable-type
        if remote.execute(pcs_cmd)['exit_code'] == 0:
            # Pacemaker service found
            ntp = NtpPacemaker(remote, node_name, admin_ip)
        elif remote.execute(systemd_cmd)['exit_code'] == 0:
            ntp = NtpSystemd(remote, node_name, admin_ip)
        else:
            # Pacemaker not found, using native ntpd
            ntp = NtpInitscript(remote, node_name, admin_ip)
        # pylint: enable=redefined-variable-type

        # Speedup time synchronization for slaves that use admin node as a peer
        if admin_ip:
            cmd = (
                "sed -i 's/^server {0} .*/server {0} minpoll 3 maxpoll 5 "
                "iburst/' /etc/ntp.conf".format(admin_ip))
            remote.execute(cmd)

        return ntp

    def __init__(self, env, node_names):
        """Context manager for synchronize time on nodes

           param: env - environment object
           param: node_names - list of devops node names
        """
        if not env:
            raise Exception("'env' is not set, failed to initialize"
                            " connections to {0}".format(node_names))
        self.admin_ntps = []
        self.pacemaker_ntps = []
        self.other_ntps = []

        admin_ip = get_admin_ip(env)

        for node_name in node_names:
            if node_name == 'admin':
                # 1. Add a 'Ntp' instance with connection to Fuel admin node
                self.admin_ntps.append(
                    self.get_ntp(get_admin_remote(env), 'admin'))
                logger.debug("Added node '{0}' to self.admin_ntps"
                             .format(node_name))
                continue
            ntp = self.get_ntp(
                get_node_remote(env, node_name), node_name, admin_ip)
            if ntp.is_pacemaker:
                # 2. Create a list of 'Ntp' connections to the controller nodes
                self.pacemaker_ntps.append(ntp)
                logger.debug("Added node '{0}' to self.pacemaker_ntps"
                             .format(node_name))
            else:
                # 2. Create a list of 'Ntp' connections to the other nodes
                self.other_ntps.append(ntp)
                logger.debug("Added node '{0}' to self.other_ntps"
                             .format(node_name))

    def __enter__(self):
        return self

    def __exit__(self, exp_type, exp_value, traceback):
        for ntp in self.admin_ntps:
            ntp.remote.clear()
        for ntp in self.pacemaker_ntps:
            ntp.remote.clear()
        for ntp in self.other_ntps:
            ntp.remote.clear()

    @staticmethod
    def is_synchronized(ntps):
        return all([ntp.is_synchronized for ntp in ntps])

    @staticmethod
    def is_connected(ntps):
        return all([ntp.is_connected for ntp in ntps])

    @staticmethod
    def report_not_synchronized(ntps):
        return [(ntp.node_name, ntp.date)
                for ntp in ntps if not ntp.is_synchronized]

    @staticmethod
    def report_not_connected(ntps):
        return [(ntp.node_name, ntp.peers)
                for ntp in ntps if not ntp.is_connected]

    @staticmethod
    def report_node_names(ntps):
        return [ntp.node_name for ntp in ntps]

    def do_sync_time(self, ntps):
        # 0. 'ntps' can be filled by __init__() or outside the class
        if not ntps:
            raise ValueError("No servers were provided to synchronize "
                             "the time in self.ntps")

        # 1. Stop NTPD service on nodes
        logger.debug("Stop NTPD service on nodes {0}"
                     .format(self.report_node_names(ntps)))
        for ntp in ntps:
            ntp.stop()

        # 2. Set actual time on all nodes via 'ntpdate'
        logger.debug("Set actual time on all nodes via 'ntpdate' on nodes {0}"
                     .format(self.report_node_names(ntps)))
        for ntp in ntps:
            ntp.set_actual_time()

        if not self.is_synchronized(ntps):
            raise TimeoutError("Time on nodes was not set with 'ntpdate':\n{0}"
                               .format(self.report_not_synchronized(ntps)))

        # 3. Start NTPD service on nodes
        logger.debug("Start NTPD service on nodes {0}"
                     .format(self.report_node_names(ntps)))
        for ntp in ntps:
            ntp.start()

        # 4. Wait for established peers
        logger.debug("Wait for established peers on nodes {0}"
                     .format(self.report_node_names(ntps)))

        for ntp in ntps:
            ntp.wait_peer()

        if not self.is_connected(ntps):
            raise TimeoutError("NTPD on nodes was not synchronized:\n"
                               "{0}".format(self.report_not_connected(ntps)))
