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
import yaml

from devops.helpers.helpers import _get_file_size


def yaml_template_load(config_file):
    def yaml_include(loader, node):
        file_name = os.path.join(os.path.dirname(loader.name), node.value)
        with file(file_name) as inputfile:
            return yaml.load(inputfile)

    def yaml_get_env_variable(loader, node):
        if not node.value.strip():
            raise ValueError("Environment variable is required after {tag} in "
                             "{filename}".format(tag=node.tag,
                                                 filename=loader.name))
        node_value = node.value.split(',', 1)
        # Get the name of environment variable
        env_variable = node_value[0].strip()

        # Get the default value for environment variable if it exists in config
        if len(node_value) > 1:
            default_val = node_value[1].strip()
        else:
            default_val = None

        value = os.environ.get(env_variable, default_val)
        if value is None:
            raise ValueError("Environment variable {var} is not set from shell"
                             " environment! No default value provided in file "
                             "{filename}".format(var=env_variable,
                                                 filename=loader.name))

        return str(value)

    yaml.add_constructor("!include", yaml_include)
    yaml.add_constructor("!os_env", yaml_get_env_variable)

    res = yaml.load(open(config_file))
    return res


def get_devops_config(filename):
    import devops
    config_file = os.path.join(os.path.dirname(devops.__file__),
                               'templates', filename)
    return yaml_template_load(config_file)


def create_admin_config(admin_vcpu, admin_memory, boot_device_order,
                        admin_sysvolume_capacity, admin_iso_path,
                        iso_device, iso_bus, interfaceorder,
                        networks_bonding=None,
                        networks_bondinginterfaces=None):

    if networks_bonding:
        ifaces = {
            label: iname
            for iname in networks_bondinginterfaces
            for label in networks_bondinginterfaces[iname]
        }
        admin_interfaces = [
            {
                'label': label,
                'l2_network_device': ifaces[label]
            } for label in sorted(ifaces.keys())
        ]
    else:
        admin_interfaces = [
            {
                'label': 'eth' + str(n),
                'l2_network_device': iname
            } for n, iname in enumerate(interfaceorder)
        ]

    admin_node = {
        'name': 'admin',  # Custom name of VM for Fuel admin node
        'role': 'fuel_admin',  # Fixed role for (Fuel admin) node properties
        'params': {
            'vcpu': admin_vcpu,
            'memory': admin_memory,
            'boot': boot_device_order,
            'volumes': [
                {
                    'name': 'system',
                    'capacity': admin_sysvolume_capacity,
                    'format': 'qcow2',
                },
                {
                    'name': 'iso',
                    'source_image': admin_iso_path,
                    'capacity': _get_file_size(admin_iso_path),
                    'format': 'raw',
                    'device': iso_device,
                    'bus': iso_bus,
                },
            ],
            'interfaces': admin_interfaces,
        },
    }
    return admin_node


def create_devops_config(boot_from,
                         env_name,
                         admin_vcpu,
                         admin_memory,
                         admin_sysvolume_capacity,
                         admin_iso_path,
                         nodes_count,
                         slave_vcpu,
                         slave_memory,
                         slave_volume_capacity,
                         use_all_disks,
                         ironic_nodes_count,
                         networks_bonding,
                         networks_bondinginterfaces,
                         networks_multiplenetworks,
                         networks_nodegroups,
                         networks_interfaceorder,
                         networks_pools,
                         networks_forwarding,
                         networks_dhcp):

    if networks_bonding:
        interfaceorder = networks_bondinginterfaces.keys()
    else:
        interfaceorder = networks_interfaceorder

    address_pools = {
        iname: {
            'net': ':'.join(networks_pools[iname])
        } for iname in interfaceorder
    }

    l2_network_devices = {
        iname: {
            'address_pool': iname,
            'dhcp': networks_dhcp[iname],
            'forward': {
                'mode': networks_forwarding[iname],
            }
        } for iname in interfaceorder
    }

    config_nodes = []

    if boot_from == 'cdrom':
        boot_device_order = ['hd', 'cdrom']
        iso_device = 'cdrom'
        iso_bus = 'ide'
    elif boot_from == 'usb':
        boot_device_order = ['hd']
        iso_device = 'disk'
        iso_bus = 'usb'

    admin_node = create_admin_config(
        admin_vcpu=admin_vcpu,
        admin_memory=admin_memory,
        boot_device_order=boot_device_order,
        admin_sysvolume_capacity=admin_sysvolume_capacity,
        admin_iso_path=admin_iso_path,
        iso_device=iso_device,
        iso_bus=iso_bus,
        interfaceorder=interfaceorder,
        networks_bonding=networks_bonding,
        networks_bondinginterfaces=networks_bondinginterfaces)

    config_nodes.append(admin_node)

    for slave_n in range(1, nodes_count):
        slave_name = 'slave-{0:0>2}'.format(slave_n)

        if networks_multiplenetworks:
            nodegroups_idx = (slave_n - 1) % 2
            slave_interfaces = [
                {
                    'label': 'eth' + str(n),
                    'l2_network_device': iname
                } for n, iname in enumerate(
                    networks_nodegroups[nodegroups_idx]['pools'])
            ]
        elif networks_bonding:
            ifaces = {
                label: iname
                for iname in networks_bondinginterfaces
                for label in networks_bondinginterfaces[iname]
            }
            slave_interfaces = [
                {
                    'label': label,
                    'l2_network_device': ifaces[label]
                } for label in sorted(ifaces.keys())
            ]
        else:
            slave_interfaces = [
                {
                    'label': 'eth' + str(n),
                    'l2_network_device': iname
                } for n, iname in enumerate(interfaceorder)
            ]

        slave_node = {
            'name': slave_name,
            'role': 'fuel_slave',
            'params': {
                'vcpu': slave_vcpu,
                'memory': slave_memory,
                'boot': ['network', 'hd'],
                'volumes': [
                    {
                        'name': 'system',
                        'capacity': slave_volume_capacity,
                    },
                ],
                'interfaces': slave_interfaces,
            },
        }
        if use_all_disks:
            slave_node['params']['volumes'].extend([
                {
                    'name': 'cinder',
                    'capacity': slave_volume_capacity
                },
                {
                    'name': 'swift',
                    'capacity': slave_volume_capacity
                }
            ])

        config_nodes.append(slave_node)

    for ironic_n in range(1, ironic_nodes_count + 1):
        ironic_name = 'ironic-slave-{0:0>2}'.format(ironic_n)
        ironic_node = {
            'name': ironic_name,
            'role': 'ironic',
            'params': {
                'vcpu': slave_vcpu,
                'memory': slave_memory,
                'boot': ['network', 'hd'],
                'volumes': [
                    {
                        'name': 'system',
                        'capacity': slave_volume_capacity,
                    },
                ],
                'interfaces': [
                    {
                        'label': 'eth0',
                        'l2_network_device': 'ironic'
                    },
                ],
            },
        }

        config_nodes.append(ironic_node)

    config = {
        'template':
            {
                'devops_settings':
                    {
                        'env_name': env_name,
                        'address_pools': address_pools,
                        'groups': [
                            {
                                'name': 'rack-01',
                                'l2_network_devices': l2_network_devices,
                                'nodes': config_nodes,
                            },
                        ]
                    }
            }
    }

    return config
