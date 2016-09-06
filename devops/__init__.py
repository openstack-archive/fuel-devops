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
import logging
import logging.config
from devops.settings import LOGS_DIR
from devops.settings import LOGS_SIZE

__version__ = '3.0.2'

if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

LOGGER_SETTINGS = {
    'version': 1,
    'disable_existing_loggers': False,
    'loggers': {
        'devops': {
            'level': 'DEBUG',
            'handlers': ['log_file', 'console_output'],
        },
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
            'filename': os.path.join(LOGS_DIR, 'devops.log'),
            'encoding': 'utf8',
            'mode': 'a',
            'maxBytes': LOGS_SIZE,
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

# Mute debug from packages
logging.getLogger('paramiko.transport').setLevel(logging.WARNING)
logging.getLogger('paramiko.hostkeys').setLevel(logging.WARNING)
logging.getLogger('keystoneauth.session').setLevel(logging.WARNING)
