#    Copyright 2013 - 2014 Mirantis, Inc.
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

_boolean_states = {'1': True, 'yes': True, 'true': True, 'on': True,
                   '0': False, 'no': False, 'false': False, 'off': False}


def get_var_as_bool(name, default):
    value = os.environ.get(name, '')
    return _boolean_states.get(value.lower(), default)

DRIVER = 'devops.driver.libvirt.libvirt_driver'
DRIVER_PARAMETERS = {
    'connection_string': os.environ.get('CONNECTION_STRING', 'qemu:///system'),
    'storage_pool_name': os.environ.get('STORAGE_POOL_NAME', 'default'),
    'stp': True,
    'hpet': False,
    'use_host_cpu': get_var_as_bool('DRIVER_USE_HOST_CPU', True),
}

INSTALLED_APPS = ['south', 'devops']

DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DEVOPS_DB_ENGINE',
                                 'django.db.backends.postgresql_psycopg2'),
        'NAME': os.environ.get('DEVOPS_DB_NAME', 'fuel_devops'),
        'USER': os.environ.get('DEVOPS_DB_USER', 'fuel_devops'),
        'PASSWORD': os.environ.get('DEVOPS_DB_PASSWORD', 'fuel_devops'),
        'HOST': os.environ.get('DEVOPS_DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DEVOPS_DB_PORT', '5432'),
        'TEST_CHARSET': os.environ.get('DEVOPS_DB_CHARSET', 'UTF8')
    }
}

KEYSTONE_CREDS = {'username': os.environ.get('KEYSTONE_USERNAME', 'admin'),
                  'password': os.environ.get('KEYSTONE_PASSWORD', 'admin'),
                  'tenant_name': os.environ.get('KEYSTONE_TENANT', 'admin')}

SSH_CREDENTIALS = {
    'admin_network': os.environ.get('ENV_ADMIN_NETWORK', 'admin'),
    'login': os.environ.get('ENV_FUEL_LOGIN', 'root'),
    'password': os.environ.get('ENV_FUEL_PASSWORD', 'r00tme')
}

SSH_SLAVE_CREDENTIALS = {
    'admin_network': os.environ.get('ENV_ADMIN_NETWORK', 'admin'),
    'login': os.environ.get('ENV_SLAVE_LOGIN', 'root'),
    'password': os.environ.get('ENV_SLAVE_PASSWORD', 'r00tme')
}

SECRET_KEY = 'dummykey'

VNC_PASSWORD = os.environ.get('VNC_PASSWORD', None)

# Default timezone for clear logging
TIME_ZONE = 'UTC'

REBOOT_TIMEOUT = os.environ.get('REBOOT_TIMEOUT', None)

DEFAULT_DOMAIN = 'domain.local'
DEFAULT_DNS = '8.8.8.8'
DEFAULT_MASTER_HOSTNAME = 'nailgun'
DEFAULT_MASTER_FQDN = "{hostname}.{domain}".format(
    hostname=DEFAULT_MASTER_HOSTNAME,
    domain=DEFAULT_DOMAIN)

MASTER_FQDN = os.environ.get('MASTER_FQDN', DEFAULT_MASTER_FQDN)
MASTER_DNS = os.environ.get('MASTER_DNS', DEFAULT_DNS)

DEFAULT_MASTER_BOOTSTRAP_LOG = '/var/log/puppet/bootstrap_admin_node.log'

MASTER_BOOTSTRAP_LOG = os.environ.get('MASTER_BOOTSTRAP_LOG',
                                      DEFAULT_MASTER_BOOTSTRAP_LOG)

USE_HUGEPAGES = get_var_as_bool('USE_HUGEPAGES', False)

try:
    from local_settings import *  # noqa
except ImportError:
    pass

#
# Settings migrated from Fuel system tests
#

OPENSTACK_RELEASE_CENTOS = 'centos'
OPENSTACK_RELEASE_UBUNTU = 'ubuntu'
OPENSTACK_RELEASE = os.environ.get(
    'OPENSTACK_RELEASE', OPENSTACK_RELEASE_CENTOS).lower()

NODE_VOLUME_SIZE = int(os.environ.get('NODE_VOLUME_SIZE', 50))
ADMIN_NODE_VOLUME_SIZE = int(os.environ.get('ADMIN_NODE_VOLUME_SIZE', 75))
ENV_NAME = os.environ.get("ENV_NAME", "fuel_system_test")

DEFAULT_INTERFACE_ORDER = 'admin,public,management,private,storage'
INTERFACE_ORDER = os.environ.get('INTERFACE_ORDER',
                                 DEFAULT_INTERFACE_ORDER).split(',')

BONDING = get_var_as_bool("BONDING", False)
BONDING_INTERFACES = {
    'admin': ['eth0', 'eth1'],
    'public': ['eth2', 'eth3', 'eth4', 'eth5']
}

MULTIPLE_NETWORKS = get_var_as_bool('MULTIPLE_NETWORKS', False)

if MULTIPLE_NETWORKS:
    NODEGROUPS = (
        {
            'name': 'default',
            'pools': ['admin', 'public', 'management', 'private',
                      'storage']
        },
        {
            'name': 'group-custom-1',
            'pools': ['admin2', 'public2', 'management2', 'private2',
                      'storage2']
        }
    )
    FORWARD_DEFAULT = os.environ.get('FORWARD_DEFAULT', 'route')
    ADMIN_FORWARD = os.environ.get('ADMIN_FORWARD', 'nat')
    PUBLIC_FORWARD = os.environ.get('PUBLIC_FORWARD', 'nat')
else:
    NODEGROUPS = ()
    FORWARD_DEFAULT = os.environ.get('FORWARD_DEFAULT', None)
    ADMIN_FORWARD = os.environ.get('ADMIN_FORWARD', FORWARD_DEFAULT or 'nat')
    PUBLIC_FORWARD = os.environ.get('PUBLIC_FORWARD', FORWARD_DEFAULT or 'nat')

POOL_DEFAULT = os.environ.get('POOL_DEFAULT', '10.109.0.0/16:24')
POOL_ADMIN = os.environ.get('POOL_ADMIN', POOL_DEFAULT)
POOL_PUBLIC = os.environ.get('POOL_PUBLIC', POOL_DEFAULT)
POOL_MANAGEMENT = os.environ.get('POOL_MANAGEMENT', POOL_DEFAULT)
POOL_PRIVATE = os.environ.get('POOL_PRIVATE', POOL_DEFAULT)
POOL_STORAGE = os.environ.get('POOL_STORAGE', POOL_DEFAULT)

DEFAULT_POOLS = {
    'admin': POOL_ADMIN,
    'public': POOL_PUBLIC,
    'management': POOL_MANAGEMENT,
    'private': POOL_PRIVATE,
    'storage': POOL_STORAGE,
}

POOLS = {
    'admin': os.environ.get(
        'PUBLIC_POOL',
        DEFAULT_POOLS.get('admin')).split(':'),
    'public': os.environ.get(
        'PUBLIC_POOL',
        DEFAULT_POOLS.get('public')).split(':'),
    'management': os.environ.get(
        'PRIVATE_POOL',
        DEFAULT_POOLS.get('management')).split(':'),
    'private': os.environ.get(
        'INTERNAL_POOL',
        DEFAULT_POOLS.get('private')).split(':'),
    'storage': os.environ.get(
        'NAT_POOL',
        DEFAULT_POOLS.get('storage')).split(':'),
}

MGMT_FORWARD = os.environ.get('MGMT_FORWARD', FORWARD_DEFAULT)
PRIVATE_FORWARD = os.environ.get('PRIVATE_FORWARD', FORWARD_DEFAULT)
STORAGE_FORWARD = os.environ.get('STORAGE_FORWARD', FORWARD_DEFAULT)

FORWARDING = {
    'admin': ADMIN_FORWARD,
    'public': PUBLIC_FORWARD,
    'management': MGMT_FORWARD,
    'private': PRIVATE_FORWARD,
    'storage': STORAGE_FORWARD,
}

# May be one of virtio, e1000, pcnet, rtl8139
INTERFACE_MODEL = os.environ.get('INTERFACE_MODEL', 'e1000')

DHCP = {
    'admin': False,
    'public': False,
    'management': False,
    'private': False,
    'storage': False,
}

NODES_COUNT = int(os.environ.get('NODES_COUNT', 10))
IRONIC_NODES_COUNT = int(os.environ.get('IRONIC_NODES_COUNT', 0))

HARDWARE = {
    "admin_node_memory": int(os.environ.get("ADMIN_NODE_MEMORY", 3072)),
    "admin_node_cpu": int(os.environ.get("ADMIN_NODE_CPU", 2)),
    "slave_node_cpu": int(os.environ.get("SLAVE_NODE_CPU", 2)),
    "slave_node_memory": int(os.environ.get("SLAVE_NODE_MEMORY", 3027)),
}

USE_ALL_DISKS = get_var_as_bool('USE_ALL_DISKS', True)
ISO_PATH = os.environ.get('ISO_PATH')

IRONIC_ENABLED = get_var_as_bool('IRONIC_ENABLED', False)

if IRONIC_ENABLED:
    POOL_IRONIC = os.environ.get('POOL_IRONIC', POOL_DEFAULT)
    IRONIC_FORWARD = os.environ.get('IRONIC_FORWARD', FORWARD_DEFAULT)
    FORWARDING['ironic'] = IRONIC_FORWARD
    DHCP['ironic'] = False
    POOLS['ironic'] = POOL_IRONIC.split(':')
    INTERFACE_ORDER.append('ironic')

if MULTIPLE_NETWORKS:
    FORWARDING['admin2'] = ADMIN_FORWARD
    FORWARDING['public2'] = PUBLIC_FORWARD
    FORWARDING['management2'] = MGMT_FORWARD
    FORWARDING['private2'] = PRIVATE_FORWARD
    FORWARDING['storage2'] = STORAGE_FORWARD

    DHCP['admin2'] = False
    DHCP['public2'] = False
    DHCP['management2'] = False
    DHCP['private2'] = False
    DHCP['storage2'] = False

    POOL_DEFAULT2 = os.environ.get('POOL_DEFAULT2', '10.109.0.0/16:24')
    POOL_ADMIN2 = os.environ.get('POOL_ADMIN2', POOL_DEFAULT2)
    POOL_PUBLIC2 = os.environ.get('POOL_PUBLIC2', POOL_DEFAULT2)
    POOL_MANAGEMENT2 = os.environ.get('POOL_MANAGEMENT', POOL_DEFAULT2)
    POOL_PRIVATE2 = os.environ.get('POOL_PRIVATE', POOL_DEFAULT2)
    POOL_STORAGE2 = os.environ.get('POOL_STORAGE', POOL_DEFAULT2)

    CUSTOM_POOLS = {
        'admin2': POOL_ADMIN2,
        'public2': POOL_PUBLIC2,
        'management2': POOL_MANAGEMENT2,
        'private2': POOL_PRIVATE2,
        'storage2': POOL_STORAGE2,
    }

    POOLS['admin2'] = os.environ.get(
        'PUBLIC_POOL2',
        CUSTOM_POOLS.get('admin2')).split(':')
    POOLS['public2'] = os.environ.get(
        'PUBLIC_POOL2',
        CUSTOM_POOLS.get('public2')).split(':')
    POOLS['management2'] = os.environ.get(
        'PUBLIC_POOL2',
        CUSTOM_POOLS.get('management2')).split(':')
    POOLS['private2'] = os.environ.get(
        'PUBLIC_POOL2',
        CUSTOM_POOLS.get('private2')).split(':')
    POOLS['storage2'] = os.environ.get(
        'PUBLIC_POOL2',
        CUSTOM_POOLS.get('storage2')).split(':')

    CUSTOM_INTERFACE_ORDER = os.environ.get(
        'CUSTOM_INTERFACE_ORDER',
        'admin2,public2,management2,private2,storage2')
    INTERFACE_ORDER.extend(CUSTOM_INTERFACE_ORDER.split(','))

# Path to the YAML file with 'devops_settings' template
# export DEVOPS_SETTINGS_TEMPLATE = /.../10-nodes-3-disks-kvm-fuel-iso.yaml
DEVOPS_SETTINGS_TEMPLATE = os.environ.get('DEVOPS_SETTINGS_TEMPLATE', None)

# Enable making external snapshots
SNAPSHOTS_EXTERNAL = get_var_as_bool('SNAPSHOTS_EXTERNAL', False)
SNAPSHOTS_EXTERNAL_DIR = os.environ.get("SNAPSHOTS_EXTERNAL_DIR",
                                        os.path.expanduser("~/.devops/snap"))
