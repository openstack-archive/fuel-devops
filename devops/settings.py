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

DRIVER = 'devops.driver.libvirt.libvirt_driver'
DRIVER_PARAMETERS = {
    'connection_string': os.environ.get('CONNECTION_STRING', 'qemu:///system'),
    'storage_pool_name': os.environ.get('STORAGE_POOL_NAME', 'default'),
    'stp': True,
    'hpet': False,
}

INSTALLED_APPS = ['south', 'devops']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'devops',
        'USER': 'postgres',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
        'TEST_CHARSET': 'UTF8'
    }
}

SSH_CREDENTIALS = {
    'admin_network': os.environ.get('ENV_ADMIN_NETWORK', 'admin'),
    'login': os.environ.get('ENV_FUEL_LOGIN', 'root'),
    'password': os.environ.get('ENV_FUEL_PASSWORD', 'r00tme')
}

SECRET_KEY = 'dummykey'

VNC_PASSWORD = os.environ.get('VNC_PASSWORD', None)

# Default timezone for clear logging
TIME_ZONE = 'UTC'

REBOOT_TIMEOUT = os.environ.get('REBOOT_TIMEOUT', None)

try:
    from local_settings import *  # noqa
except ImportError:
    pass

#
# Settings migrated from Fuel system tests
#

NODE_VOLUME_SIZE = int(os.environ.get('NODE_VOLUME_SIZE', 50))
