#    Copyright 2013 - 2016 Mirantis, Inc.
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
import time
import logging.config
from devops import settings

__version__ = '3.0.5'

if not os.path.exists(settings.LOGS_DIR):
    os.makedirs(settings.LOGS_DIR)

LOGGER_SETTINGS = {
    'version': 1,
    'disable_existing_loggers': False,
    'loggers': {
        'devops': {
            'level': 'DEBUG',
            'handlers': ['log_file', 'console_output'],
        },
        'paramiko': {'level': 'WARNING'},
        'iso8601': {'level': 'WARNING'},
        'keystoneauth': {'level': 'WARNING'},
    },
    'handlers': {
        'console_output': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'default',
            'stream': 'ext://sys.stdout',
        },
        'log_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'DEBUG',
            'formatter': 'default',
            'filename': os.path.join(settings.LOGS_DIR, 'devops.log'),
            'encoding': 'utf8',
            'mode': 'a',
            'maxBytes': settings.LOGS_SIZE,
            'backupCount': 5,
        },
    },
    'formatters': {
        'default': {
            'format': '%(asctime)s - %(levelname)s - %(filename)s:'
                      '%(lineno)d -- %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
}

logging.config.dictConfig(LOGGER_SETTINGS)
# set logging timezone to GMT
logging.Formatter.converter = time.gmtime
logger = logging.getLogger(__name__)
