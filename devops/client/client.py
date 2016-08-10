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

from devops.client.environment import DevopsEnvironment
from devops.helpers.templates import create_devops_config
from devops.helpers.templates import get_devops_config
from devops.models.environment import Environment
from devops import settings


class DevopsClient(object):
    """Client class

    Provide methods to get/create environments
    """

    def get_env(self, env_name):
        env = Environment.get(name=env_name)
        return DevopsEnvironment(env)

    def list_env_names(self):
        return [env.name for env in Environment.list_all()]

    def synchronize_all(self):
        Environment.synchronize_all()

    def create_env_from_config(self, config):
        """Creates env from template

        :type config: str or dict
        """
        if isinstance(config, str):
            config = get_devops_config(config)

        env = Environment.create_environment(config)
        return DevopsEnvironment(env)

    def create_env(self,
                   boot_from='cdrom',
                   env_name=None,
                   admin_iso_path=None,
                   admin_vcpu=None,
                   admin_memory=None,
                   admin_sysvolume_capacity=None,
                   nodes_count=None,
                   slave_vcpu=None,
                   slave_memory=None,
                   second_volume_capacity=None,
                   third_volume_capacity=None,
                   net_pool=None):
        """Backward compatibility for fuel-qa

        Creates env from list of environment variables
        """
        if net_pool:
            net_pool = net_pool.split(':')

        hw = settings.HARDWARE

        config = create_devops_config(
            boot_from=boot_from,
            env_name=env_name or settings.ENV_NAME,
            admin_vcpu=admin_vcpu or hw['admin_node_cpu'],
            admin_memory=admin_memory or hw['admin_node_memory'],
            admin_sysvolume_capacity=(
                admin_sysvolume_capacity or settings.ADMIN_NODE_VOLUME_SIZE),
            admin_iso_path=admin_iso_path or settings.ISO_PATH,
            nodes_count=nodes_count or settings.NODES_COUNT,
            numa_nodes=hw['numa_nodes'],
            slave_vcpu=slave_vcpu or hw['slave_node_cpu'],
            slave_memory=slave_memory or hw["slave_node_memory"],
            slave_volume_capacity=settings.NODE_VOLUME_SIZE,
            second_volume_capacity=(
                second_volume_capacity or settings.NODE_VOLUME_SIZE),
            third_volume_capacity=(
                third_volume_capacity or settings.NODE_VOLUME_SIZE),
            use_all_disks=settings.USE_ALL_DISKS,
            multipath_count=settings.SLAVE_MULTIPATH_DISKS_COUNT,
            ironic_nodes_count=settings.IRONIC_NODES_COUNT,
            networks_bonding=settings.BONDING,
            networks_bondinginterfaces=settings.BONDING_INTERFACES,
            networks_multiplenetworks=settings.MULTIPLE_NETWORKS,
            networks_nodegroups=settings.NODEGROUPS,
            networks_interfaceorder=settings.INTERFACE_ORDER,
            networks_pools=dict(
                admin=net_pool or settings.POOLS['admin'],
                public=net_pool or settings.POOLS['public'],
                management=net_pool or settings.POOLS['management'],
                private=net_pool or settings.POOLS['private'],
                storage=net_pool or settings.POOLS['storage'],
            ),
            networks_forwarding=settings.FORWARDING,
            networks_dhcp=settings.DHCP,
            driver_enable_acpi=settings.DRIVER_PARAMETERS['enable_acpi'],
            driver_enable_nwfilers=settings.ENABLE_LIBVIRT_NWFILTERS,
        )
        return self.create_env_from_config(config)
