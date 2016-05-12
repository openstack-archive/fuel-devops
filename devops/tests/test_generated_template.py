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

# pylint: disable=no-self-use

import yaml

from django.test import TestCase


from devops.helpers.templates import create_devops_config
from devops import settings


class TestDefaultTemplate(TestCase):

    def test_default(self):
        config = create_devops_config(
            boot_from='cdrom',
            env_name=settings.ENV_NAME,
            admin_vcpu=settings.HARDWARE["admin_node_cpu"],
            admin_memory=settings.HARDWARE["admin_node_memory"],
            admin_sysvolume_capacity=settings.ADMIN_NODE_VOLUME_SIZE,
            admin_iso_path=settings.ISO_PATH,
            nodes_count=2,
            numa_nodes=settings.HARDWARE['numa_nodes'],
            slave_vcpu=settings.HARDWARE["slave_node_cpu"],
            slave_memory=settings.HARDWARE["slave_node_memory"],
            slave_volume_capacity=settings.NODE_VOLUME_SIZE,
            second_volume_capacity=settings.NODE_VOLUME_SIZE,
            third_volume_capacity=settings.NODE_VOLUME_SIZE,
            use_all_disks=settings.USE_ALL_DISKS,
            ironic_nodes_count=settings.IRONIC_NODES_COUNT,
            networks_bonding=settings.BONDING,
            networks_bondinginterfaces=settings.BONDING_INTERFACES,
            networks_multiplenetworks=settings.MULTIPLE_NETWORKS,
            networks_nodegroups=settings.NODEGROUPS,
            networks_interfaceorder=settings.INTERFACE_ORDER,
            networks_pools=settings.POOLS,
            networks_forwarding=settings.FORWARDING,
            networks_dhcp=settings.DHCP,
            driver_enable_acpi=settings.DRIVER_PARAMETERS['enable_acpi'],
        )
        r = yaml.dump(config, indent=2, default_flow_style=False)
        assert r == """template:
  devops_settings:
    address_pools:
      admin:
        net: 10.109.0.0/16:24
        params:
          ip_ranges:
            default:
            - 2
            - -2
          ip_reserved:
            gateway: 1
            l2_network_device: 1
      management:
        net: 10.109.0.0/16:24
        params:
          ip_ranges:
            default:
            - 2
            - -2
          ip_reserved:
            gateway: 1
            l2_network_device: 1
      private:
        net: 10.109.0.0/16:24
        params:
          ip_ranges:
            default:
            - 2
            - -2
          ip_reserved:
            gateway: 1
            l2_network_device: 1
      public:
        net: 10.109.0.0/16:24
        params:
          ip_ranges:
            default:
            - 2
            - 127
            floating:
            - 128
            - -2
          ip_reserved:
            gateway: 1
            l2_network_device: 1
      storage:
        net: 10.109.0.0/16:24
        params:
          ip_ranges:
            default:
            - 2
            - -2
          ip_reserved:
            gateway: 1
            l2_network_device: 1
    env_name: fuel_system_test
    groups:
    - driver:
        name: devops.driver.libvirt
        params:
          connection_string: qemu:///system
          enable_acpi: false
          hpet: false
          storage_pool_name: default
          stp: true
          use_host_cpu: true
      l2_network_devices:
        admin:
          address_pool: admin
          dhcp: false
          forward:
            mode: nat
        management:
          address_pool: management
          dhcp: false
          forward:
            mode: null
        private:
          address_pool: private
          dhcp: false
          forward:
            mode: null
        public:
          address_pool: public
          dhcp: false
          forward:
            mode: nat
        storage:
          address_pool: storage
          dhcp: false
          forward:
            mode: null
      name: default
      network_pools:
        fuelweb_admin: admin
        management: management
        private: private
        public: public
        storage: storage
      nodes:
      - name: admin
        params:
          boot:
          - hd
          - cdrom
          bootmenu_timeout: 0
          interfaces:
          - interface_model: e1000
            l2_network_device: admin
            label: iface0
          - interface_model: e1000
            l2_network_device: public
            label: iface1
          - interface_model: e1000
            l2_network_device: management
            label: iface2
          - interface_model: e1000
            l2_network_device: private
            label: iface3
          - interface_model: e1000
            l2_network_device: storage
            label: iface4
          memory: 3072
          network_config:
            iface0:
              networks:
              - fuelweb_admin
            iface1:
              networks:
              - public
            iface2:
              networks:
              - management
            iface3:
              networks:
              - private
            iface4:
              networks:
              - storage
          numa: []
          vcpu: 2
          volumes:
          - capacity: 75
            format: qcow2
            name: system
          - bus: ide
            device: cdrom
            format: raw
            name: iso
            source_image: null
        role: fuel_master
      - name: slave-01
        params:
          boot:
          - network
          - hd
          interfaces:
          - interface_model: e1000
            l2_network_device: admin
            label: iface0
          - interface_model: e1000
            l2_network_device: public
            label: iface1
          - interface_model: e1000
            l2_network_device: management
            label: iface2
          - interface_model: e1000
            l2_network_device: private
            label: iface3
          - interface_model: e1000
            l2_network_device: storage
            label: iface4
          memory: 3027
          network_config:
            iface0:
              networks:
              - fuelweb_admin
            iface1:
              networks:
              - public
            iface2:
              networks:
              - management
            iface3:
              networks:
              - private
            iface4:
              networks:
              - storage
          numa: []
          vcpu: 2
          volumes:
          - capacity: 50
            name: system
          - capacity: 50
            name: cinder
          - capacity: 50
            name: swift
        role: fuel_slave
"""

    def test_acpi_and_numa(self):
        config = create_devops_config(
            boot_from='cdrom',
            env_name=settings.ENV_NAME,
            admin_vcpu=4,
            admin_memory=16 * 1024,
            admin_sysvolume_capacity=settings.ADMIN_NODE_VOLUME_SIZE,
            admin_iso_path=settings.ISO_PATH,
            nodes_count=2,
            numa_nodes=2,
            slave_vcpu=8,
            slave_memory=32 * 1024,
            slave_volume_capacity=settings.NODE_VOLUME_SIZE,
            second_volume_capacity=settings.NODE_VOLUME_SIZE,
            third_volume_capacity=settings.NODE_VOLUME_SIZE,
            use_all_disks=settings.USE_ALL_DISKS,
            ironic_nodes_count=settings.IRONIC_NODES_COUNT,
            networks_bonding=settings.BONDING,
            networks_bondinginterfaces=settings.BONDING_INTERFACES,
            networks_multiplenetworks=settings.MULTIPLE_NETWORKS,
            networks_nodegroups=settings.NODEGROUPS,
            networks_interfaceorder=settings.INTERFACE_ORDER,
            networks_pools=settings.POOLS,
            networks_forwarding=settings.FORWARDING,
            networks_dhcp=settings.DHCP,
            driver_enable_acpi=True,
        )
        r = yaml.dump(config, indent=2, default_flow_style=False)
        assert r == """template:
  devops_settings:
    address_pools:
      admin:
        net: 10.109.0.0/16:24
        params:
          ip_ranges:
            default:
            - 2
            - -2
          ip_reserved:
            gateway: 1
            l2_network_device: 1
      management:
        net: 10.109.0.0/16:24
        params:
          ip_ranges:
            default:
            - 2
            - -2
          ip_reserved:
            gateway: 1
            l2_network_device: 1
      private:
        net: 10.109.0.0/16:24
        params:
          ip_ranges:
            default:
            - 2
            - -2
          ip_reserved:
            gateway: 1
            l2_network_device: 1
      public:
        net: 10.109.0.0/16:24
        params:
          ip_ranges:
            default:
            - 2
            - 127
            floating:
            - 128
            - -2
          ip_reserved:
            gateway: 1
            l2_network_device: 1
      storage:
        net: 10.109.0.0/16:24
        params:
          ip_ranges:
            default:
            - 2
            - -2
          ip_reserved:
            gateway: 1
            l2_network_device: 1
    env_name: fuel_system_test
    groups:
    - driver:
        name: devops.driver.libvirt
        params:
          connection_string: qemu:///system
          enable_acpi: true
          hpet: false
          storage_pool_name: default
          stp: true
          use_host_cpu: true
      l2_network_devices:
        admin:
          address_pool: admin
          dhcp: false
          forward:
            mode: nat
        management:
          address_pool: management
          dhcp: false
          forward:
            mode: null
        private:
          address_pool: private
          dhcp: false
          forward:
            mode: null
        public:
          address_pool: public
          dhcp: false
          forward:
            mode: nat
        storage:
          address_pool: storage
          dhcp: false
          forward:
            mode: null
      name: default
      network_pools:
        fuelweb_admin: admin
        management: management
        private: private
        public: public
        storage: storage
      nodes:
      - name: admin
        params:
          boot:
          - hd
          - cdrom
          bootmenu_timeout: 0
          interfaces:
          - interface_model: e1000
            l2_network_device: admin
            label: iface0
          - interface_model: e1000
            l2_network_device: public
            label: iface1
          - interface_model: e1000
            l2_network_device: management
            label: iface2
          - interface_model: e1000
            l2_network_device: private
            label: iface3
          - interface_model: e1000
            l2_network_device: storage
            label: iface4
          memory: 16384
          network_config:
            iface0:
              networks:
              - fuelweb_admin
            iface1:
              networks:
              - public
            iface2:
              networks:
              - management
            iface3:
              networks:
              - private
            iface4:
              networks:
              - storage
          numa:
          - cpus: 0,1
            memory: 8192
          - cpus: 2,3
            memory: 8192
          vcpu: 4
          volumes:
          - capacity: 75
            format: qcow2
            name: system
          - bus: ide
            device: cdrom
            format: raw
            name: iso
            source_image: null
        role: fuel_master
      - name: slave-01
        params:
          boot:
          - network
          - hd
          interfaces:
          - interface_model: e1000
            l2_network_device: admin
            label: iface0
          - interface_model: e1000
            l2_network_device: public
            label: iface1
          - interface_model: e1000
            l2_network_device: management
            label: iface2
          - interface_model: e1000
            l2_network_device: private
            label: iface3
          - interface_model: e1000
            l2_network_device: storage
            label: iface4
          memory: 32768
          network_config:
            iface0:
              networks:
              - fuelweb_admin
            iface1:
              networks:
              - public
            iface2:
              networks:
              - management
            iface3:
              networks:
              - private
            iface4:
              networks:
              - storage
          numa:
          - cpus: 0,1,2,3
            memory: 16384
          - cpus: 4,5,6,7
            memory: 16384
          vcpu: 8
          volumes:
          - capacity: 50
            name: system
          - capacity: 50
            name: cinder
          - capacity: 50
            name: swift
        role: fuel_slave
"""
