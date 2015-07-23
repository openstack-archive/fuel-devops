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

import os
import subprocess

from devops import error
from devops.helpers.retry import retry
from devops import logger as LOGGER


class DevopsDriver(object):
    def __getattr__(self, name):
        """Default method for all unimplemented functions."""
        def default_method(*args, **kwargs):
            LOGGER.debug('Call of unimplemented method detected. '
                         'Method is {0}{1}{2}'.format(name, args, kwargs))
        return default_method

    def __init__(self, **driver_parameters):
        # self.ipmi_cmd = ['/usr/bin/ipmitool', '-l', 'lan']
        self.ipmi_cmd = driver_parameters.get(
            'ipmi_cmd',
            '/usr/bin/ipmitool -I lan').split()
        self._check_system_ready()

    def _check_system_ready(self):
        must_have_commands = [
            '/usr/bin/ipmitool'
        ]
        for command in must_have_commands:
            if not os.path.isfile(command):
                raise error.DevopsEnvironmentError(command)
        return True

    def _ipmi(self, node, command):
        if node.uri.find('://'):
            schema, resource = node.uri.split('://')
            if 'ipmi' not in schema:
                raise TypeError("IPMI protocol dosn't set")
            else:
                ipmi_cred, ipmi_host = resource.split('@')
                ipmi_host = ipmi_host.rstrip('/')
                ipmi_user, ipmi_password = ipmi_cred.split(':')
        else:
            raise TypeError("IPMI protocol dosn't set")
        cmd = self.ipmi_cmd + ['-H', ipmi_host,
                               '-U', ipmi_user,
                               '-P', ipmi_password] + command
        return subprocess.check_output(cmd)

    def node_reset(self, node):
        LOGGER.debug('Resetting server via IPMI')
        output = self._ipmi(node, ['power', 'reset'])
        LOGGER.debug('Reset output: %s' % output)
        return True

    def node_reboot(self, node):
        LOGGER.debug('Reboot server via IPMI')
        output = self._ipmi(node, ['power', 'cycle'])
        LOGGER.debug('Reboot server output: {0}'.format(output))
        return True

    def node_shutdown(self, node):
        LOGGER.debug('Off server via IPMI')
        output = self._ipmi(node, ['power', 'off'])
        LOGGER.debug('Off server output: {0}'.format(output))
        return True

    def get_node_power(self, node):
        LOGGER.debug('Get server power')
        output = self._ipmi(node, ['power', 'status'])
        LOGGER.debug('Set boot server output: {0}'.format(output))
        return output

    def node_destroy(self, node):
        return self.node_shutdown(node)

    def node_create(self, node):
        return self.node_start(node)

    def node_start(self, node):
        LOGGER.debug('On server via IPMI')
        output = self._ipmi(node, ['power', 'on'])
        LOGGER.debug('On server output: {0}'.format(output))
        return True

    def node_power_status(self, node):
        LOGGER.debug('Get server power')
        output = self._ipmi(node, ['power', 'status'])
        LOGGER.debug('Set boot server output: {0}'.format(output))
        return output.split()[3]

    def node_active(self, node):
        """Check if node is active

        :type node: Node
            :rtype : Boolean
        """
        return 'on' in self.node_power_status(node)

    @retry(20, 30)
    def set_node_boot(self, node, device):
        """Set boot device

        :param node: devops.Node
        :param device: calid are: 'pxe' or 'disk'
            :rtype: bool
        """
        if device not in set('pxe', 'disk'):
            raise AttributeError
        LOGGER.debug('Set boot device to %s' % device)
        output = self._ipmi(node, ['chassis', 'bootdev', device])
        LOGGER.debug('Set boot server output: {0}'.format(output))
        return True

    def node_snapshot_exists(self, node, name):
        LOGGER.info('Trying check snapshot on baremetal node')
        return False

    def node_get_snapshots(self, node):
        LOGGER.info('Trying get list of snapshot on baremetal node')
        return None

    def node_create_snapshot(self, node, name=None, description=None):
        LOGGER.info('Trying create snapshot on baremetal node')
        return True

    def node_revert_snapshot(self, node, name=None):
        LOGGER.info('Trying revert baremetal node from snapshot')
        return False

    def node_delete_all_snapshots(self, node):
        LOGGER.info('Trying cleanup revert baremetal node from snapshot')
        return False

    def node_delete_snapshot(self, node, name=None):
        LOGGER.info('Trying remove snapshot on baremetal node')
        return False

    def node_define(self, node):
        LOGGER.info('Define baremetal node')
        status = self.get_node_power(node)
        if status:
            return True
        else:
            return False
