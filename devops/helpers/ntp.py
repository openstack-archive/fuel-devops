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
def sync_time(env, node_names):
    """Synchronize time on nodes

       param: env - environment object
       param: node_names - list of devops node names
    """
    with GroupNtpSync(env, node_names) as g_ntp:
        g_ntp.do_sync_time()


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
        self.ntps = []

        # 1. Add a 'Ntp' instance with connection to Fuel admin node
        if 'admin' in node_names:
            self.ntps.append(
                Ntp.get_ntp(get_admin_remote(env), 'admin'))

        admin_ip = get_admin_ip(env)

        # 2. Create a list of 'Ntp' connections to the nodes
        self.ntps.extend([
            Ntp.get_ntp(get_node_remote(env, node_name), node_name, admin_ip)
            for node_name in node_names if node_name != 'admin'])

    def __enter__(self):
        return self

    def __exit__(self, exp_type, exp_value, traceback):
        [ntp.remote.clear() for ntp in self.ntps]

    @property
    def is_synchronized(self):
        return all([ntp.is_synchronized for ntp in self.ntps])

    @property
    def is_connected(self):
        return all([ntp.is_connected for ntp in self.ntps])

    def report_not_synchronized(self):
        return [(ntp.node_name, ntp.date())
                for ntp in self.ntps if not ntp.is_synchronized]

    def report_not_connected(self):
        return [(ntp.node_name, ntp.peers)
                for ntp in self.ntps if not ntp.is_connected]

    def do_sync_time(self, ntps=None):
        # 0. 'ntps' can be filled by __init__() or outside the class
        self.ntps = ntps or self.ntps
        if not self.ntps:
            raise ValueError("No servers were provided to synchronize "
                             "the time in self.ntps")

        # 1. Stop NTPD service on nodes
        [ntp.stop() for ntp in self.ntps]

        # 2. Set actual time on all nodes via 'ntpdate'
        [ntp.set_actual_time() for ntp in self.ntps]
        if not self.is_synchronized:
            raise TimeoutError("Time on nodes was not set with 'ntpdate':\n"
                               "{0}".format(self.report_not_synchronized()))

        # 3. Start NTPD service on nodes
        [ntp.start() for ntp in self.ntps]

        # 4. Wait for established peers
        [ntp.wait_peer() for ntp in self.ntps]
        if not self.is_connected:
            raise TimeoutError("NTPD on nodes was not synchronized:\n"
                               "{0}".format(self.report_not_connected()))

        # 5. Report time on nodes
        for ntp in self.ntps:
            print("Time on '{0}' = {1}".format(ntp.node_name,
                                               ntp.date()[0].rstrip()))


class Ntp(object):
    """Common methods to work with ntpd service."""

    @staticmethod
    def get_ntp(remote, node_name='node', admin_ip=None):

        # Detect how NTPD is managed - by init script or by pacemaker.
        cmd = "ps -C pacemakerd && crm_resource --resource p_ntp --locate"

        if remote.execute(cmd)['exit_code'] == 0:
            # Pacemaker service found
            cls = NtpPacemaker()
        else:
            # Pacemaker not found, using native ntpd
            cls = NtpInitscript()

        cls.is_synchronized = False
        cls.is_connected = False
        cls.remote = remote
        cls.node_name = node_name
        cls.peers = []

        # Get IP of a server from which the time will be syncronized.
        cmd = "awk '/^server/ && $2 !~ /127.*/ {print $2}' /etc/ntp.conf"
        cls.server = remote.execute(cmd)['stdout'][0]

        cmd = "find /etc/init.d/ -regex '/etc/init.d/ntp.?'"
        cls.service = remote.execute(cmd)['stdout'][0].strip()

        # Speedup time synchronization for slaves that use admin node as a peer
        if admin_ip:
            cmd = ("sed -i 's/^server {0} .*/server {0} minpoll 3 maxpoll 5 "
                   "ibrust/' /etc/ntp.conf".format(admin_ip))
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

                # 2. remote should be marked whith tally  '*'
                if remote[0] != '*':
                    continue

                # 3. reachability bit array should have '1' at least in
                # two lower bits as the last two sussesful checks
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
