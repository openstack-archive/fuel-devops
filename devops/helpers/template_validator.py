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

import importlib
import os

from jsonschema import Draft4Validator as Validator
import yaml

from devops.error import TemplateValidatorError
from devops import logger
from devops import TEMPLATES_DIR


class TemplateValidator(object):
    """Validator for template files.

    Base schema located in:
    devops/templates/schema.yaml

    It contains main elements of template except any driver specific
    fields and parameters.

    Driver specific schemas should be located in driver's directory.
    For example, schema for libvirt driver located in:
    devops/driver/libvirt/schema.yaml


    validator is based on jsonschema library.
    More info and examples can be found here:
    http://json-schema.org/example2.html
    http://spacetelescope.github.io/understanding-json-schema/index.html
    """

    SCHEMA_FNAME = 'schema.yaml'

    def __init__(self):
        self.errors = []
        self.template_schema = self._load_template_schema()

    def _get_validator(self, schema):
        Validator.check_schema(schema)
        return Validator(schema)

    def _load_yaml(self, fpath):
        with open(fpath) as f:
            return yaml.load(f)

    def _load_driver_schema(self, driver_name):
        driver_mod = importlib.import_module(driver_name)
        driver_dir = os.path.dirname(os.path.abspath(driver_mod.__file__))
        return self._load_yaml(os.path.join(driver_dir, self.SCHEMA_FNAME))

    def _load_template_schema(self):
        return self._load_yaml(os.path.join(TEMPLATES_DIR, self.SCHEMA_FNAME))

    def _get_global_links(self, config):
        links = {}
        links['address_pool'] = {
            'type': 'string',
            'enum': config.get('address_pools', {}).keys(),
        }
        l2devs = []
        links['l2_network_device'] = {
            'type': 'string',
            'enum': l2devs,
        }
        for group in config.get('groups', []):
            l2devs += group.get('l2_network_devices', {}).keys()
        return links

    def _get_group_links(self, group):
        links = {}
        links['network_pool'] = {
            'type': 'string',
            'enum': group.get('network_pools', {}).keys(),
        }
        return links

    def _get_node_links(self, node_params):
        links = {}
        links['interface'] = {
            'type': 'string',
            'enum': [interface.get('label')
                     for interface in node_params.get('interfaces', [])],
        }
        return links

    def validate(self, full_config):
        self.errors = []
        config = full_config['template']['devops_settings']

        # build links
        self.global_links = self._get_global_links(config)
        self.template_schema['definitions']['links'] = self.global_links

        # validate
        v = Validator(self.template_schema)
        for error in v.iter_errors(full_config):
            self.errors.append(('Error in main template', error))

        # validate group content
        for group_num, group in enumerate(config['groups']):
            self._validate_group(group_num, group)

        for msg, error in self.errors:
            logger.error(msg)
            logger.error(error)

        if self.errors:
            raise TemplateValidatorError(
                '{} Error(s) in template'.format(len(self.errors)))

    def _validate_group(self, group_num, group):
        self.group_links = self._get_group_links(group)
        self.group_links.update(self.global_links)
        self.driver_schema = self._load_driver_schema(group['driver']['name'])

        self._validate_driver_params(group_num, group)
        self._validate_l2_network_devices(group_num, group)
        self._validate_nodes(group_num, group)

    def _validate_driver_params(self, group_num, group):
        driver_params_schema = self.driver_schema['driver_params']
        driver_params_schema['definitions'] = dict()
        driver_params_schema['definitions']['links'] = self.group_links
        driver_params = group['driver']['params']

        v = self._get_validator(driver_params_schema)
        for error in v.iter_errors(driver_params):
            msg = ('Error in config["template"]["devops_settings"]'
                   '["groups"][{}]["driver"]["params"]'.format(group_num))
            self.errors.append((msg, error))

    def _validate_l2_network_devices(self, group_num, group):
        l2_network_device_schema = self.driver_schema['l2_network_device']
        l2_network_device_schema['definitions'] = dict()
        l2_network_device_schema['definitions']['links'] = self.group_links

        v = self._get_validator(l2_network_device_schema)

        for l2_dev_name, l2_dev in group['l2_network_devices'].iteritems():
            for error in v.iter_errors(l2_dev):
                msg = ('Error in config["template"]["devops_settings"]'
                       '["groups"][{}]["l2_network_devices"][{}]'
                       ''.format(group_num, l2_dev_name))
                self.errors.append((msg, error))

    def _validate_nodes(self, group_num, group):
        node_params_schema = self.driver_schema['node_params']

        nodes = group['nodes']
        for node_num, node in enumerate(nodes):
            node_params = node['params']

            node_links = self._get_node_links(node_params)
            node_links.update(self.group_links)

            node_params_schema['definitions'] = dict()
            node_params_schema['definitions']['links'] = node_links

            v = self._get_validator(node_params_schema)
            for error in v.iter_errors(node_params):
                msg = ('Error in config["template"]["devops_settings"]'
                       '["groups"][{}]["nodes"][{}]["params"]'
                       ''.format(group_num, node_num))
                self.errors.append((msg, error))
