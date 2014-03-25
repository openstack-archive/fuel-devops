#    Copyright 2014 Mirantis, Inc.
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
import yaml
import logging
import logging.config


log_path = (os.environ.get('DEVOPS_LOG_CONFIG', os.curdir),
            os.path.dirname(os.path.abspath(__file__)),
            os.path.join(os.path.expanduser("~"), '.devops'),
            '/etc/devops')
for loc in log_path:
    try:
        with open(os.path.join(loc, 'log.yaml')) as f:
            config = yaml.load(f.read())
            # Create log folders
            for h in config['handlers'].values():
                if h.get('filename'):
                    h['filename'] = os.path.expanduser(h['filename'])
                    directory = os.path.dirname(h['filename'])
                    if not os.path.exists(directory):
                        os.makedirs(directory)

            logging.config.dictConfig(config)
            break
    except IOError:
        pass

logger = logging.getLogger(__name__)
