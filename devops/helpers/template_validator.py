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

import jsonschema

from devops import logger
from devops.helpers import loader


_template_schema = {
    '$schema': 'http://json-schema.org/draft-05/schema#',
    'description': 'Schema for devops environment template',
    'type': 'object',
    'required': ['template'],
    'properties': {
        'template': {
            'type': 'object',
            'required': ['devops_settings'],
            'properties': {
                'devops_settings': {
                    'type': 'object',
                    'additionalProperties': False,
                    'required': ['env_name', 'address_pools', 'groups'],
                    'properties': {
                        'address_pools': {
                            'type': 'object',
                            'patternProperties': {
                                '^\\S+$': {
                                    '$ref': '#/definitions/address_pool'
                                }
                            },
                        },
                        'env_name': {'type': 'string'},
                        'groups': {
                            'type': 'array',
                            'minItems': 1,
                            'items': {'$ref': '#/definitions/group'},
                        }
                    },
                }
            },
        }
    },

    'definitions': {

        'address_pool': {
            'type': 'object',
            'additionalProperties': False,
            'required': ['net'],
            'properties': {
                'net': {
                    'type': 'string',
                    'pattern': (
                        '^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}'
                        '(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'
                        '\\/(?:3[0-2]|[12][0-9]|[1-9])'
                        '\\:(?:3[0-2]|[12][0-9]|[1-9])$'),
                },
                'params': {
                    'type': 'object',
                    'properties': {
                        'tag': {'type': 'integer'}
                    },
                }
            },
        },

        'group': {
            'type': 'object',
            'required': [
                'name',
                'driver',
                'network_pools',
                'l2_network_devices',
                'nodes'
            ],
            'properties': {
                'driver': {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string'},
                        'params': {'type': 'object'}
                    },
                },
                'l2_network_devices': {
                    'type': 'object',
                    'additionalProperties': False,
                    'patternProperties': {
                        '^\\S+$': {
                            '$ref': '#/definitions/l2_network_device'
                        }
                    },
                },
                'name': {'type': 'string'},
                'network_pools': {
                    'type': 'object',
                    'additionalProperties': False,
                    'patternProperties': {
                        '^\\S+$': {'type': 'string'}
                    },
                },
                'nodes': {
                    'type': 'array',
                    'minItems': 1,
                    'items': {'$ref': '#/definitions/node'},
                }
            },
        },

        'l2_network_device': {
            'properties': {
                'address_pool': {'type': 'string'},
                'dhcp': {'type': 'boolean'},
                'forward': {
                    'properties': {
                        'mode': {
                            'enum': ['nat'],
                            'type': 'string'
                        }
                    },
                    'type': 'object'
                }
            },
            'required': ['address_pool', 'dhcp'],
            'type': 'object'
        },

        'node': {
            'properties': {
                'name': {'type': 'string'},
                'params': {'type': 'object'},
                'role': {'type': 'string'}
            },
            'required': ['name', 'role', 'params'],
            'type': 'object'
        }
    },
}


def validate(full_config):
    # validate general config
    try:
        jsonschema.validate(full_config, _template_schema)
    except jsonschema.ValidationError as e:
        logger.error('Error in template')
        logger.error(e)
        return False

    config = full_config['template']['devops_settings']
    groups = config['groups']
    for group_num, group in enumerate(groups):
        driver_name = group['driver']['name']
        DriverCls = loader.load_class(driver_name)

        driver_params = group['driver']['params']

        # validate driver params
        try:
            jsonschema.validate(driver_params, DriverCls.params_schema)
        except jsonschema.ValidationError as e:
            logger.error('Error in config["template"]["devops_settings"]'
                         '["groups"][{}]["driver"]["params"]'
                         ''.format(group_num))
            logger.error(e)
            return False

        NodeCls = DriverCls.get_model_class('Node')

        nodes = group['nodes']
        for node_num, node in enumerate(nodes):
            node_params = node['params']

            # validate node params
            try:
                jsonschema.validate(node_params, NodeCls.params_schema)
            except jsonschema.ValidationError as e:
                logger.error('Error in config["template"]["devops_settings"]'
                             '["groups"][{}]["nodes"][{}]["params"]'
                             ''.format(group_num, node_num))
                logger.error(e)
                return False

    return True
