#    Copyright 2015-2016 Mirantis, Inc.
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

from __future__ import division

import os

from netaddr import IPNetwork
import yaml

from devops.error import DevopsError


def yaml_template_load(config_file):
    def yaml_include(loader, node):
        file_name = os.path.join(os.path.dirname(loader.name), node.value)
        if not os.path.isfile(file_name):
            raise ValueError(
                "Cannot load the environment template {0} : include file {1} "
                "doesn't exist.".format(config_file, file_name))
        with open(file_name) as inputfile:
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

        return yaml.load(value)

    if not os.path.isfile(config_file):
        raise ValueError(
            "Cannot load the environment template {0} : file "
            "doesn't exist.".format(config_file))

    yaml.add_constructor("!include", yaml_include)
    yaml.add_constructor("!os_env", yaml_get_env_variable)

    return yaml.load(open(config_file))


def get_devops_config(filename):
    """Read the YAML file and create a 'full_config' object.

    :param filename: path to a file that contains a YAML template
        :rtype: dict
    """
    import devops
    config_file = os.path.join(os.path.dirname(devops.__file__),
                               'templates', filename)
    return yaml_template_load(config_file)


def create_admin_config(admin_vcpu, admin_memory, admin_sysvolume_capacity,
                        admin_iso_path, boot_from, interfaceorder,
                        numa_nodes,
                        networks_bonding=None,
                        networks_bondinginterfaces=None):

    if networks_bonding:
        # DEPRECATED. Use YAML template for test cases with bonding.
        # For fuel-qa bonding cases, 'network_config' is hardcoded in the tests
        # (see self.INTERFACES in fuel-qa 'test_bonding_base.py')
        # Translate a dict of lists {net_name: [eth0, eth1],} into a new dict:
        # {eth0: net_name, eth1: net_name,}
        ifaces = {
            label: iname
            for iname in networks_bondinginterfaces
            for label in networks_bondinginterfaces[iname]
        }
        admin_interfaces = [
            {
                'label': label,
                'l2_network_device': ifaces[label],
                'interface_model': 'e1000',
            } for label in sorted(ifaces.keys())
        ]
        # Please use YAML templates instead of old-style tests to make new
        # tests for bonds.
    else:
        admin_interfaces = [
            {
                'label': 'iface' + str(n),
                'l2_network_device': iname,
                'interface_model': 'e1000',
            } for n, iname in enumerate(interfaceorder)
        ]

    # network_config is for storing OpenStack networks mapping on interfaces
    # based on 'interfaceorder' object.
    # Resulting object will be (by default):
    #   network_config:
    #     iface0:
    #       networks:
    #        - fuelweb_admin
    #     iface1:
    #       networks:
    #        - public
    #     iface2:
    #       networks:
    #        - storage
    #     iface3:
    #       networks:
    #        - management
    #     iface4:
    #       networks:
    #        - private
    network_config = {
        iface['label']: {
            'networks': [
                iface['l2_network_device']
                if iface['l2_network_device'] != 'admin'
                else 'fuelweb_admin',
            ]
        } for iface in admin_interfaces
    }

    if boot_from == 'usb':
        boot_device_order = ['hd']
        iso_device = 'disk'
        iso_bus = 'usb'
        bootmenu_timeout = 3000
    else:  # boot_from == 'cdrom':
        boot_device_order = ['hd', 'cdrom']
        iso_device = 'cdrom'
        iso_bus = 'ide'
        bootmenu_timeout = 0

    numa = _calculate_numa(
        numa_nodes=numa_nodes,
        vcpu=admin_vcpu,
        memory=admin_memory,
        name='admin')

    admin_config = {
        'name': 'admin',  # Custom name of VM for Fuel admin node
        'role': 'fuel_master',  # Fixed role for (Fuel admin) node properties
        'params': {
            'vcpu': admin_vcpu,
            'memory': admin_memory,
            'boot': boot_device_order,
            'bootmenu_timeout': bootmenu_timeout,
            'numa': numa,
            'volumes': [
                {
                    'name': 'system',
                    'capacity': admin_sysvolume_capacity,
                    'format': 'qcow2',
                },
                {
                    'name': 'iso',
                    'source_image': admin_iso_path,
                    'format': 'raw',
                    'device': iso_device,
                    'bus': iso_bus,
                },
            ],
            'interfaces': admin_interfaces,
            'network_config': network_config,
        },
    }
    return admin_config


def create_slave_config(slave_name, slave_role, slave_vcpu, slave_memory,
                        slave_volume_capacity,
                        interfaceorder,
                        numa_nodes,
                        second_volume_capacity=None,
                        third_volume_capacity=None,
                        use_all_disks=False,
                        networks_multiplenetworks=None,
                        networks_nodegroups=None,
                        networks_bonding=None,
                        networks_bondinginterfaces=None):

    if networks_multiplenetworks:
        nodegroups_idx = 1 - int(slave_name[-2:]) % 2
        slave_interfaces = [
            {
                'label': 'iface' + str(n),
                'l2_network_device': iname,
                'interface_model': 'e1000',
            } for n, iname in enumerate(
                networks_nodegroups[nodegroups_idx]['pools'])
        ]
    elif networks_bonding:
        # DEPRECATED. Use YAML template for test cases with bonding.
        # For fuel-qa bonding cases, 'network_config' is hardcoded in the tests
        # (see self.INTERFACES in fuel-qa 'test_bonding_base.py')
        # Translate a dict of lists {net_name: [eth0, eth1],} into a new dict:
        # {eth0: net_name, eth1: net_name,}
        ifaces = {
            label: iname
            for iname in networks_bondinginterfaces
            for label in networks_bondinginterfaces[iname]
        }
        slave_interfaces = [
            {
                'label': label,
                'l2_network_device': ifaces[label],
                'interface_model': 'e1000',
            } for label in sorted(ifaces.keys())
        ]
    else:
        slave_interfaces = [
            {
                'label': 'iface' + str(n),
                'l2_network_device': iname,
                'interface_model': 'e1000',
            } for n, iname in enumerate(interfaceorder)
        ]

    # network_config is for storing OpenStack networks mapping on interfaces
    # based on 'interfaceorder' object.
    # Resulting object will be (by default):
    #   network_config:
    #     iface0:
    #       networks:
    #        - fuelweb_admin
    #     iface1:
    #       networks:
    #        - public
    #     iface2:
    #       networks:
    #        - storage
    #     iface3:
    #       networks:
    #        - management
    #     iface4:
    #       networks:
    #        - private
    network_config = {
        iface['label']: {
            'networks': [
                iface['l2_network_device']
                if iface['l2_network_device'] != 'admin'
                else 'fuelweb_admin',
            ]
        } for iface in slave_interfaces
    }

    volumes = [
        {
            'name': 'system',
            'capacity': slave_volume_capacity,
        }
    ]
    if use_all_disks:
        volumes.extend([
            {
                'name': 'cinder',
                'capacity': second_volume_capacity or slave_volume_capacity
            },
            {
                'name': 'swift',
                'capacity': third_volume_capacity or slave_volume_capacity
            }
        ])
    else:
        if second_volume_capacity:
            volumes.append(
                {
                    'name': 'cinder',
                    'capacity': second_volume_capacity
                }
            )
        if third_volume_capacity:
            volumes.append(
                {
                    'name': 'swift',
                    'capacity': third_volume_capacity
                }
            )

    numa = _calculate_numa(
        numa_nodes=numa_nodes,
        vcpu=slave_vcpu,
        memory=slave_memory,
        name=slave_name)

    slave_config = {
        'name': slave_name,
        'role': slave_role,
        'params': {
            'vcpu': slave_vcpu,
            'memory': slave_memory,
            'boot': ['network', 'hd'],
            'numa': numa,
            'volumes': volumes,
            'interfaces': slave_interfaces,
            'network_config': network_config,
        },
    }
    return slave_config


def create_netpools(interfaceorder):
    netpool = {}
    for iname in interfaceorder:
        if iname == 'admin':
            netname = 'fuelweb_admin'
        else:
            netname = iname
        netpool[netname] = iname
    return netpool


def create_address_pools(interfaceorder, networks_pools):
    address_pools = {
        iname: {
            'net': ':'.join(networks_pools[iname]),
            'params': {
                'ip_reserved': {
                    # Gateway will be used for configure OpenStack networks
                    'gateway': 1,
                    # l2_network_device will be used for configure local bridge
                    'l2_network_device': 1,
                },
                'ip_ranges': {
                    'default': [2, -2],
                },
            },
        } for iname in interfaceorder
    }

    if 'public' in interfaceorder:
        # Put floating IP range for public network
        default_pool_name = 'default'
        floating_pool_name = 'floating'

        # Take a first subnet with necessary size and calculate the size
        net = IPNetwork(networks_pools['public'][0])
        new_prefix = int(networks_pools['public'][1])
        subnet = next(net.subnet(prefixlen=new_prefix))
        network_size = subnet.size

        address_pools['public']['params']['ip_ranges'][default_pool_name] = [
            2, network_size // 2 - 1]
        address_pools['public']['params']['ip_ranges'][floating_pool_name] = [
            network_size // 2, -2]

    return address_pools


def create_l2_network_devices(interfaceorder,
                              networks_dhcp,
                              networks_forwarding):
    l2_network_devices = {
        iname: {
            'address_pool': iname,
            'dhcp': networks_dhcp[iname],
            'forward': {
                'mode': networks_forwarding[iname],
            }
        } for iname in interfaceorder
    }
    return l2_network_devices


def _calculate_numa(numa_nodes, vcpu, memory, name):
    numa = []
    if numa_nodes:
        cpus_per_numa = vcpu // numa_nodes
        if cpus_per_numa * numa_nodes != vcpu:
            raise DevopsError(
                "NUMA_NODES={0} is not a multiple of the number of CPU={1}"
                " for node '{2}'".format(numa_nodes, vcpu, name))
        memory_per_numa = memory // numa_nodes
        if memory_per_numa * numa_nodes != memory:
            raise DevopsError(
                "NUMA_NODES={0} is not a multiple of the amount of "
                "MEMORY={1} for node '{2}'".format(numa_nodes,
                                                   memory,
                                                   name))
        for x in range(numa_nodes):
            # List of cpu IDs for the numa node
            cpus = range(x * cpus_per_numa, (x + 1) * cpus_per_numa)
            cell = {
                'cpus': ','.join(map(str, cpus)),
                'memory': memory_per_numa,
            }
            numa.append(cell)

    return numa


def create_devops_config(boot_from,
                         env_name,
                         admin_vcpu,
                         admin_memory,
                         admin_sysvolume_capacity,
                         admin_iso_path,
                         nodes_count,
                         numa_nodes,
                         slave_vcpu,
                         slave_memory,
                         slave_volume_capacity,
                         second_volume_capacity,
                         third_volume_capacity,
                         use_all_disks,
                         ironic_nodes_count,
                         networks_bonding,
                         networks_bondinginterfaces,
                         networks_multiplenetworks,
                         networks_nodegroups,
                         networks_interfaceorder,
                         networks_pools,
                         networks_forwarding,
                         networks_dhcp,
                         driver_enable_acpi):
    """Creates devops config object

    This method is used for backward compatibility with old-style
    environment creation, where most of environment parameters were
    passed with shell environment variables.

    See models/environment.py and settings.py for details about
    input parameters structure.
    """

    # If bonding enabled, then a different interfaces order is provided.
    if networks_bonding:
        interfaceorder = networks_bondinginterfaces.keys()
    else:
        interfaceorder = networks_interfaceorder

    # Create address pools object
    address_pools = create_address_pools(interfaceorder, networks_pools)
    netpools = create_netpools(interfaceorder)

    # Create network devices object
    l2_network_devices = create_l2_network_devices(interfaceorder,
                                                   networks_dhcp,
                                                   networks_forwarding)
    # Create admin and slave nodes
    config_nodes = []

    admin_config = create_admin_config(
        admin_vcpu=admin_vcpu,
        admin_memory=admin_memory,
        admin_sysvolume_capacity=admin_sysvolume_capacity,
        admin_iso_path=admin_iso_path,
        boot_from=boot_from,
        numa_nodes=numa_nodes,
        interfaceorder=interfaceorder,
        networks_bonding=networks_bonding,
        networks_bondinginterfaces=networks_bondinginterfaces)

    config_nodes.append(admin_config)

    for slave_n in range(1, nodes_count):
        slave_name = 'slave-{0:0>2}'.format(slave_n)

        slave_config = create_slave_config(
            slave_name=slave_name,
            slave_role='fuel_slave',
            slave_vcpu=slave_vcpu,
            slave_memory=slave_memory,
            slave_volume_capacity=slave_volume_capacity,
            second_volume_capacity=second_volume_capacity,
            third_volume_capacity=third_volume_capacity,
            interfaceorder=interfaceorder,
            numa_nodes=numa_nodes,
            use_all_disks=use_all_disks,
            networks_multiplenetworks=networks_multiplenetworks,
            networks_nodegroups=networks_nodegroups,
            networks_bonding=networks_bonding,
            networks_bondinginterfaces=networks_bondinginterfaces)

        config_nodes.append(slave_config)

    for ironic_n in range(1, ironic_nodes_count + 1):
        ironic_name = 'ironic-slave-{0:0>2}'.format(ironic_n)

        ironic_config = create_slave_config(
            slave_name=ironic_name,
            slave_role='ironic_slave',
            slave_vcpu=slave_vcpu,
            slave_memory=slave_memory,
            slave_volume_capacity=slave_volume_capacity,
            interfaceorder=['ironic'],
            numa_nodes=numa_nodes,
            use_all_disks=False)

        config_nodes.append(ironic_config)

    config = {
        'template': {
            'devops_settings': {
                'env_name': env_name,
                'address_pools': address_pools,
                'groups': [
                    {
                        'driver': {
                            'name':
                                'devops.driver.libvirt',
                            'params': {
                                'connection_string': 'qemu:///system',
                                'storage_pool_name': 'default',
                                'stp': True,
                                'hpet': False,
                                'use_host_cpu': True,
                                'enable_acpi': driver_enable_acpi,
                            },
                        },
                        'name': 'default',
                        'network_pools': netpools,
                        'l2_network_devices': l2_network_devices,
                        'nodes': config_nodes,
                    },
                ]
            }
        }
    }

    return config
