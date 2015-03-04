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
