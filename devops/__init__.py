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
import logging
import logging.handlers
from devops.settings import LOGS_DIR
from devops.settings import LOGS_SIZE
from logging.config import dictConfig


__version__ = '3.0.0'
DEFAULT_LOGGING = {'version': 1,
                   'disable_existing_loggers': False}

dictConfig(DEFAULT_LOGGING)

if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s %(filename)s:'
                    '%(lineno)d -- %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filename=os.path.join(LOGS_DIR, 'devops.log'),
                    filemode='a')

console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s %(filename)s:'
                              '%(lineno)d -- %(message)s')
console.setFormatter(formatter)
filename = os.path.join(LOGS_DIR, 'devops.log')
log_file = logging.handlers.RotatingFileHandler(filename,
                                                encoding='utf8',
                                                maxBytes=LOGS_SIZE,
                                                backupCount=5)
log_file.setLevel(logging.DEBUG)
log_file.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.addHandler(console)
logger.addHandler(log_file)
logger.setLevel(logging.DEBUG)
