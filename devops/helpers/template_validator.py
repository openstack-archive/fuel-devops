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
import importlib

import jsonschema
import yaml

from devops import TEMPLATES_DIR
from devops import logger


def _load_yaml(fpath):
    with open(fpath) as f:
        return yaml.load(f)


def _load_driver_schema(driver_name):
    driver_mod = importlib.import_module(driver_name)
    driver_dir = os.path.dirname(os.path.abspath(driver_mod.__file__))
    return _load_yaml(os.path.join(driver_dir, 'schema.yaml'))


def _load_template_schema():
    return _load_yaml(os.path.join(TEMPLATES_DIR, 'schema.yaml'))


def validate(full_config):
    template_schema = _load_template_schema()

    # validate general config
    try:
        jsonschema.validate(full_config, template_schema)
    except jsonschema.ValidationError as e:
        logger.error('Error in template')
        logger.error(e)
        return False

    # validate group content
    config = full_config['template']['devops_settings']
    groups = config['groups']
    for group_num, group in enumerate(groups):
        driver_schema = _load_driver_schema(group['driver']['name'])
        driver_params_schema = driver_schema['driver_params']
        driver_params = group['driver']['params']

        # validate driver params
        try:
            jsonschema.validate(driver_params, driver_params_schema)
        except jsonschema.ValidationError as e:
            logger.error('Error in config["template"]["devops_settings"]'
                         '["groups"][{}]["driver"]["params"]'
                         ''.format(group_num))
            logger.error(e)
            return False

        # validate l2 network devices
        l2_network_device_schema = driver_schema['l2_network_device']
        for l2_dev_name, l2_dev in group['l2_network_devices'].iteritems():
            try:
                jsonschema.validate(l2_dev, l2_network_device_schema)
            except jsonschema.ValidationError as e:
                logger.error('Error in config["template"]["devops_settings"]'
                             '["groups"][{}]["l2_network_devices"][{}]'
                             ''.format(group_num, l2_dev_name))
                logger.error(e)
                return False

        node_params_schema = driver_schema['node_params']

        # validate node params
        nodes = group['nodes']
        for node_num, node in enumerate(nodes):
            node_params = node['params']
            try:
                jsonschema.validate(node_params, node_params_schema)
            except jsonschema.ValidationError as e:
                logger.error('Error in config["template"]["devops_settings"]'
                             '["groups"][{}]["nodes"][{}]["params"]'
                             ''.format(group_num, node_num))
                logger.error(e)
                return False

    return True
