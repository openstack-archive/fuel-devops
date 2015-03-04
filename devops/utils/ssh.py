#    Copyright 2013 - 2015 Mirantis, Inc.
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

from devops.common.proboscis import assert_equal
from devops.decorators import retry
from devops import logger


# @logwrap
def execute_remote_cmd(remote, cmd, exit_code=0):
    result = remote.execute(cmd)
    assert_equal(result['exit_code'], exit_code,
                 'Failed to execute "{0}" on remote host: {1}'.
                 format(cmd, result))
    return result['stdout']


@retry(count=10, delay=60)
# @logwrap
def sync_node_time(remote):
    execute_remote_cmd(remote, 'hwclock -s')
    execute_remote_cmd(remote, 'NTPD=$(find /etc/init.d/ -regex \''
                               '/etc/init.d/\(ntp.?\|ntp-dev\)\');'
                               '$NTPD stop && ntpd -dqg && $NTPD '
                               'start')
    execute_remote_cmd(remote, 'hwclock -w')
    remote_date = remote.execute('date')['stdout']
    logger.info("Node time: %s" % remote_date)
