#    Copyright 2015 - 2016 Mirantis, Inc.
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
import collections
import warnings

import paramiko
import six

from devops import error
from devops.helpers import decorators
from devops.helpers import helpers
from devops import logger


@decorators.retry(paramiko.SSHException, count=3, delay=60)
def sync_time(env, node_names, skip_sync=False):
    """Synchronize time on nodes

       param: env - environment object
       param: node_names - list of devops node names
       param: skip_sync - only get the current time without sync
       return: dict{node_name: node_time, ...}
    """
    logger.warning('sync_time is deprecated. Use DevopsClient instead')
    warnings.warn(
        'sync_time is deprecated. Use DevopsClient.sync_time instead',
        DeprecationWarning)

    from devops import client
    denv = client.DevopsClient().get_env(env.name)
    return denv.sync_time(node_names=node_names, skip_sync=skip_sync)


class AbstractNtp(six.with_metaclass(abc.ABCMeta, object)):

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
        srv_cmd = "awk '/^server/ && $2 !~ /^127\./ {print $2}' /etc/ntp.conf"
        server = self.remote.execute(srv_cmd)['stdout'][0]

        # Waiting for parent server until it starts providing the time
        set_date_cmd = "ntpdate -p 4 -t 0.2 -bu {0}".format(server)
        helpers.wait(
            lambda: not self.remote.execute(set_date_cmd)['exit_code'],
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
        helpers.wait(
            self._get_sync_complete,
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
        helpers.wait(
            self._get_burst_complete, timeout=timeout,
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
            raise error.DevopsError(
                'No suitable NTP service found on node {!r}'
                ''.format(node_name))

    def __init__(self):
        self.ntp_groups = collections.defaultdict(list)

    def __enter__(self):
        return self

    def __exit__(self, exp_type, exp_value, traceback):
        pass

    def add_node(self, remote, node_name):
        group = 'other'
        if node_name == 'admin':
            group = 'admin'
            ntp = self.get_ntp(remote, 'admin')
        else:
            ntp = self.get_ntp(remote, node_name)
            if isinstance(ntp, NtpPacemaker):
                group = 'pacemaker'

        self.ntp_groups[group].append(ntp)

    def get_curr_time(self):
        return {
            ntp.node_name: ntp.date
            for ntps in self.ntp_groups.values()
            for ntp in ntps
        }

    def sync_time(self, group_name):
        if group_name not in self.ntp_groups:
            logger.debug("No ntp group: {0}".format(group_name))
            return

        ntps = self.ntp_groups[group_name]

        if not ntps:
            logger.debug("No nodes in ntp group: {0}".format(group_name))
            return

        node_names = [ntp.node_name for ntp in ntps]

        logger.debug("Stop NTP service on nodes {0}".format(node_names))
        for ntp in ntps:
            ntp.stop()

        logger.debug("Set actual time on nodes {0}".format(node_names))
        for ntp in ntps:
            ntp.set_actual_time()

        logger.debug("Start NTP service on nodes {0}".format(node_names))
        for ntp in ntps:
            ntp.start()

        logger.debug("Wait for established peers on nodes {0}".format(
            node_names))
        for ntp in ntps:
            ntp.wait_peer()

        logger.debug("time sync completted on nodes {0}".format(node_names))
