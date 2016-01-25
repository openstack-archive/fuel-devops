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

import time

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
        results = {ntp.node_name: ntp.date()[0].rstrip() for ntp in all_ntps}

    return results


class GroupNtpSync(object):
    """Synchronize a group of nodes."""

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
                    Ntp.get_ntp(get_admin_remote(env), 'admin'))
                logger.debug("Added node '{0}' to self.admin_ntps"
                             .format(node_name))
                continue
            ntp = Ntp.get_ntp(get_node_remote(env, node_name),
                              node_name, admin_ip)
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
        [ntp.remote.clear() for ntp in self.admin_ntps]
        [ntp.remote.clear() for ntp in self.pacemaker_ntps]
        [ntp.remote.clear() for ntp in self.other_ntps]

    def is_synchronized(self, ntps):
        return all([ntp.is_synchronized for ntp in ntps])

    def is_connected(self, ntps):
        return all([ntp.is_connected for ntp in ntps])

    def report_not_synchronized(self, ntps):
        return [(ntp.node_name, ntp.date())
                for ntp in ntps if not ntp.is_synchronized]

    def report_not_connected(self, ntps):
        return [(ntp.node_name, ntp.peers)
                for ntp in ntps if not ntp.is_connected]

    def report_node_names(self, ntps):
        return [ntp.node_name for ntp in ntps]

    def do_sync_time(self, ntps):
        # 0. 'ntps' can be filled by __init__() or outside the class
        if not ntps:
            raise ValueError("No servers were provided to synchronize "
                             "the time in self.ntps")

        # 1. Stop NTPD service on nodes
        logger.debug("Stop NTPD service on nodes {0}"
                     .format(self.report_node_names(ntps)))
        [ntp.stop() for ntp in ntps]

        # 2. Set actual time on all nodes via 'ntpdate'
        logger.debug("Set actual time on all nodes via 'ntpdate' on nodes {0}"
                     .format(self.report_node_names(ntps)))
        [ntp.set_actual_time() for ntp in ntps]
        if not self.is_synchronized(ntps):
            raise TimeoutError("Time on nodes was not set with 'ntpdate':\n{0}"
                               .format(self.report_not_synchronized(ntps)))

        # 3. Start NTPD service on nodes
        logger.debug("Start NTPD service on nodes {0}"
                     .format(self.report_node_names(ntps)))
        [ntp.start() for ntp in ntps]

        # 4. Wait for established peers
        logger.debug("Wait for established peers on nodes {0}"
                     .format(self.report_node_names(ntps)))
        [ntp.wait_peer() for ntp in ntps]

        if not self.is_connected(ntps):
            raise TimeoutError("NTPD on nodes was not synchronized:\n"
                               "{0}".format(self.report_not_connected(ntps)))


class Ntp(object):
    """Common methods to work with ntpd service."""

    @staticmethod
    def get_ntp(remote, node_name='node', admin_ip=None):

        # Detect how NTPD is managed - by init script or by pacemaker.
        pcs_cmd = "ps -C pacemakerd && crm_resource --resource p_ntp --locate"
        systemd_cmd = "systemctl list-unit-files| grep ntpd"

        if remote.execute(pcs_cmd)['exit_code'] == 0:
            # Pacemaker service found
            cls = NtpPacemaker()
            cls.is_pacemaker = True
        elif remote.execute(systemd_cmd)['exit_code'] == 0:
            cls = NtpSystemd()
            cls.is_pacemaker = False
        else:
            # Pacemaker not found, using native ntpd
            cls = NtpInitscript()
            cls.is_pacemaker = False
            # Find upstart / sysv-init executable script
            cmd = "find /etc/init.d/ -regex '/etc/init.d/ntp.?'"
            cls.service = remote.execute(cmd)['stdout'][0].strip()

        cls.is_synchronized = False
        cls.is_connected = False
        cls.remote = remote
        cls.node_name = node_name
        cls.peers = []

        # Get IP of a server from which the time will be synchronized.
        cmd = "awk '/^server/ && $2 !~ /127.*/ {print $2}' /etc/ntp.conf"
        cls.server = remote.execute(cmd)['stdout'][0]

        # Speedup time synchronization for slaves that use admin node as a peer
        if admin_ip:
            cmd = ("sed -i 's/^server {0} .*/server {0} minpoll 3 maxpoll 5 "
                   "iburst/' /etc/ntp.conf".format(admin_ip))
            remote.execute(cmd)

        return cls

    def set_actual_time(self, timeout=600):
        # Waiting for parent server until it starts providing the time
        cmd = "ntpdate -p 4 -t 0.2 -bu {0}".format(self.server)
        self.is_synchronized = False
        try:
            wait(lambda: not self.remote.execute(cmd)['exit_code'], timeout)
            self.remote.execute('hwclock -w')
            self.is_synchronized = True
        except TimeoutError:
            pass

        return self.is_synchronized

    def wait_peer(self, interval=8, timeout=600):
        self.is_connected = False

        start_time = time.time()
        while start_time + timeout > time.time():
            # peer = `ntpq -pn 127.0.0.1`
            self.peers = self.get_peers()[2:]  # skip the header
            logger.debug("Node: {0}, ntpd peers: {1}".format(
                self.node_name, self.peers))

            for peer in self.peers:
                p = peer.split()
                remote = str(p[0])
                reach = int(p[6], 8)   # From octal to int
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

    def date(self):
        return self.remote.execute("date")['stdout']


class NtpInitscript(Ntp):
    """NtpInitscript."""  # TODO(ddmitriev) documentation

    def start(self):
        self.is_connected = False
        self.remote.execute("{0} start".format(self.service))

    def stop(self):
        self.is_connected = False
        self.remote.execute("{0} stop".format(self.service))

    def get_peers(self):
        return self.remote.execute('ntpq -pn 127.0.0.1')['stdout']


class NtpPacemaker(Ntp):
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


class NtpSystemd(Ntp):
    """NtpSystemd."""  # TODO(ddmitriev) documentation

    def start(self):
        self.is_connected = False
        self.remote.execute('systemctl start ntpd')

    def stop(self):
        self.is_connected = False
        self.remote.execute('systemctl stop ntpd')

    def get_peers(self):
        return self.remote.execute('ntpq -pn 127.0.0.1')['stdout']
