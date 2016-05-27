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

from six import add_metaclass

from devops.error import DevopsError
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
        results = {ntp.node_name: ntp.date for ntp in all_ntps}

    return results


@add_metaclass(abc.ABCMeta)
class AbstractNtp(object):

    def __init__(self, remote, node_name):
        self._remote = remote
        self._node_name = node_name

    def __repr__(self):
        return "{0}(remote={1}, node_name={2!r})".format(
            self.__class__.__name__, self.remote, self.node_name)

    @property
    def remote(self):
        """remote object"""
        return self._remote

    @property
    def node_name(self):
        """node name"""
        return self._node_name

    @property
    def date(self):
        return self.remote.execute("date")['stdout'][0].rstrip()

    @abc.abstractmethod
    def start(self):
        """Start ntp daemon"""

    @abc.abstractmethod
    def stop(self):
        """Stop ntp daemon"""

    @abc.abstractmethod
    def set_actual_time(self, timeout=600):
        """enforce time sync"""

    @abc.abstractmethod
    def wait_peer(self, interval=8, timeout=600):
        """Wait for connection"""


# pylint: disable=abstract-method
# noinspection PyAbstractClass
class BaseNtp(AbstractNtp):
    """Base class for ntpd based services

    Provides common methods:
    - set_actual_time
    - wait_peer
    """

    def set_actual_time(self, timeout=600):
        # Get IP of a server from which the time will be synchronized.
        srv_cmd = "awk '/^server/ && $2 !~ /127.*/ {print $2}' /etc/ntp.conf"
        server = self.remote.execute(srv_cmd)['stdout'][0]

        # Waiting for parent server until it starts providing the time
        set_date_cmd = "ntpdate -p 4 -t 0.2 -bu {0}".format(server)
        wait(lambda: not self.remote.execute(set_date_cmd)['exit_code'],
             timeout=timeout,
             timeout_msg='Failed to set actual time on node {!r}'.format(
                 self._node_name))

        self.remote.check_call('hwclock -w')

    def _get_ntpq(self):
        return self.remote.execute('ntpq -pn 127.0.0.1')['stdout'][2:]

    def _get_sync_complete(self):
        peers = self._get_ntpq()

        logger.debug("Node: {0}, ntpd peers: {1}".format(
            self.node_name, peers))

        for peer in peers:
            p = peer.split()
            remote = str(p[0])
            reach = int(p[6], 8)  # From octal to int
            offset = float(p[8])
            jitter = float(p[9])

            # 1. offset and jitter should not be higher than 500
            # Otherwise, time should be re-set.
            if (abs(offset) > 500) or (abs(jitter) > 500):
                continue

            # 2. remote should be marked with tally  '*'
            if remote[0] != '*':
                continue

            # 3. reachability bit array should have '1' at least in
            # two lower bits as the last two successful checks
            if reach & 3 != 3:
                continue

            return True
        return False

    def wait_peer(self, interval=8, timeout=600):
        wait(self._get_sync_complete,
             interval=interval,
             timeout=timeout,
             timeout_msg='Failed to wait peer on node {!r}'.format(
                 self._node_name))

# pylint: enable=abstract-method


class NtpInitscript(BaseNtp):
    """NtpInitscript."""  # TODO(ddmitriev) documentation

    def __init__(self, remote, node_name):
        super(NtpInitscript, self).__init__(remote, node_name)
        get_ntp_cmd = \
            "find /etc/init.d/ -regex '/etc/init.d/ntp.?' -executable"
        result = remote.execute(get_ntp_cmd)
        self._service = result['stdout'][0].strip()

    def start(self):
        self.remote.check_call("{0} start".format(self._service))

    def stop(self):
        self.remote.check_call("{0} stop".format(self._service))


class NtpPacemaker(BaseNtp):
    """NtpPacemaker."""  # TODO(ddmitriev) documentation

    def start(self):
        # Temporary workaround of the LP bug #1441121
        self.remote.execute('ip netns exec vrouter ip l set dev lo up')

        self.remote.execute('crm resource start p_ntp')

    def stop(self):
        self.remote.execute('crm resource stop p_ntp; killall ntpd')

    def _get_ntpq(self):
        return self.remote.execute(
            'ip netns exec vrouter ntpq -pn 127.0.0.1')['stdout'][2:]


class NtpSystemd(BaseNtp):
    """NtpSystemd."""  # TODO(ddmitriev) documentation

    def start(self):
        self.remote.check_call('systemctl start ntpd')

    def stop(self):
        self.remote.check_call('systemctl stop ntpd')


class NtpChronyd(AbstractNtp):
    """Implements communication with chrony service

    Reference: http://chrony.tuxfamily.org/
    """

    def start(self):
        # No need to stop/start chronyd
        # client can't work without daemon
        pass

    def stop(self):
        # No need to stop/start chronyd
        # client can't work without daemon
        pass

    def _get_burst_complete(self):
        result = self._remote.check_call('chronyc -a activity')
        stdout = result['stdout']
        burst_line = stdout[4]
        return burst_line == '0 sources doing burst (return to online)\n'

    def set_actual_time(self, timeout=600):
        # sync time
        # 3 - good measurements
        # 5 - max measurements
        self._remote.check_call('chronyc -a burst 3/5')

        # wait burst complete
        wait(self._get_burst_complete, timeout=timeout,
             timeout_msg='Failed to set actual time on node {!r}'.format(
                 self._node_name))

        # set system clock
        self._remote.check_call('chronyc -a makestep')

    def wait_peer(self, interval=8, timeout=600):
        # wait for synchronization
        # 10 - number of tries
        # 0.01 - maximum allowed remaining correction
        self._remote.check_call('chronyc -a waitsync 10 0.01')


class GroupNtpSync(object):
    """Synchronize a group of nodes."""

    @staticmethod
    def get_ntp(remote, node_name):
        # Detect how NTPD is managed - by init script or by pacemaker.
        pcs_cmd = "ps -C pacemakerd && crm_resource --resource p_ntp --locate"
        systemd_cmd = "systemctl list-unit-files| grep ntpd"
        chronyd_cmd = "systemctl is-active chronyd"
        initd_cmd = "find /etc/init.d/ -regex '/etc/init.d/ntp.?' -executable"

        if remote.execute(pcs_cmd)['exit_code'] == 0:
            # Pacemaker service found
            return NtpPacemaker(remote, node_name)
        elif remote.execute(systemd_cmd)['exit_code'] == 0:
            return NtpSystemd(remote, node_name)
        elif remote.execute(chronyd_cmd)['exit_code'] == 0:
            return NtpChronyd(remote, node_name)
        elif len(remote.execute(initd_cmd)['stdout']):
            return NtpInitscript(remote, node_name)
        else:
            raise DevopsError('No suitable NTP service found on node {!r}'
                              ''.format(node_name))

    def __init__(self, env, node_names):
        """Context manager for synchronize time on nodes

           param: env - environment object
           param: node_names - list of devops node names
        """
        self.admin_ntps = []
        self.pacemaker_ntps = []
        self.other_ntps = []

        for node_name in node_names:
            if node_name == 'admin':
                # 1. Add a 'Ntp' instance with connection to Fuel admin node
                admin_remote = get_admin_remote(env)
                admin_ntp = self.get_ntp(admin_remote, 'admin')
                self.admin_ntps.append(admin_ntp)
                logger.debug("Added node '{0}' to self.admin_ntps"
                             .format(node_name))
                continue
            remote = get_node_remote(env, node_name)
            ntp = self.get_ntp(remote, node_name)
            if isinstance(ntp, NtpPacemaker):
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
    def report_node_names(ntps):
        return [ntp.node_name for ntp in ntps]

    def do_sync_time(self, ntps):
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
