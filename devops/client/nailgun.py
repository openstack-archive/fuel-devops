#    Copyright 2016 Mirantis, Inc.
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

from django.utils import functional
from keystoneauth1.identity import V2Password
from keystoneauth1.session import Session as KeystoneSession

from devops import error
from devops import logger
from devops import settings


class NailgunClient(object):

    def __init__(self, ip):
        self.ip = ip

    @functional.cached_property
    def _keystone_session(self):
        keystone_auth = V2Password(
            auth_url="http://{}:5000/v2.0".format(self.ip),
            username=settings.KEYSTONE_CREDS['username'],
            password=settings.KEYSTONE_CREDS['password'],
            tenant_name=settings.KEYSTONE_CREDS['tenant_name'])
        return KeystoneSession(auth=keystone_auth, verify=False)

    def get_slave_ip_by_mac(self, mac):
        nodes = self.get_nodes_json()

        def poor_mac(mac_addr):
            return [m.lower() for m in mac_addr
                    if m.lower() in '01234546789abcdef']

        for node in nodes:
            for interface in node['meta']['interfaces']:
                if poor_mac(interface['mac']) == poor_mac(mac):
                    logger.debug('For mac {0} found ip {1}'
                                 .format(mac, node['ip']))
                    return node['ip']
        raise error.DevopsError(
            'There is no match between MAC {0} and Nailgun MACs'.format(mac))

    def get_nodes_json(self):
        nodes = self._keystone_session.get(
            '/nodes',
            endpoint_filter={'service_type': 'fuel'}
        )
        return nodes.json()
