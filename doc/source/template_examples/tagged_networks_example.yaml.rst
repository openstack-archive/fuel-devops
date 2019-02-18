.. _tagged_networks_example.yaml:

YAML template for tagged networks
=================================

This template describes a configuration for environment that configured for
use tagged OpenStack networks.

All slave nodes have only two network interfaces:
 - first interface is used for 'fuelweb_admin' network (PXE provisioning)
 - second interface is used for the rest OpenStack networks. It is connected
   to the libvirt bridge 'openstack_br' that doesn't have it's own IP address
   and is used for remove tags 100, 101, 102 and 103 from the packets coming
   from this bridge, and getting untagged packets on the libvirt networks
   'public', 'management', 'storage' and 'private'.

.. code-block:: yaml

    ---
    aliases:

      dynamic_address_pool:
       - &pool_default !os_env POOL_DEFAULT, 10.90.0.0/16:24

      default_interface_model:
       - &interface_model !os_env INTERFACE_MODEL, e1000

    template:
      devops_settings:
        env_name: !os_env ENV_NAME

        address_pools:
        # Network pools used by the environment
          fuelweb_admin-pool01:
            net: *pool_default
            params:
              ip_reserved:
                gateway: +1
                default_l2_network_device: +1  # l2_network_device will get this IP address
              ip_ranges:
                default: [+2, -2]     # admin IP range for 'default' nodegroup name

          public-pool01:
            net: *pool_default
            params:
              vlan_start: 100
              ip_reserved:
                gateway: +1
                default_l2_network_device: +1  # l2_network_device will get this IP address
              ip_ranges:
                default: [+2, +127]  # public IP range for 'default' nodegroup name
                floating: [+128, -2]

          storage-pool01:
            net: *pool_default
            params:
              vlan_start: 101
          management-pool01:
            net: *pool_default
            params:
              vlan_start: 102
          private-pool01:
            net: *pool_default
            params:
              vlan_start: 103

        groups:
         - name: default
           driver:
             name: devops.driver.libvirt.libvirt_driver
             params:
               connection_string: !os_env CONNECTION_STRING, qemu:///system
               storage_pool_name: !os_env STORAGE_POOL_NAME, default
               stp: True
               hpet: False
               use_host_cpu: !os_env DRIVER_USE_HOST_CPU, true

           network_pools:  # Address pools for OpenStack networks.
             # Actual names should be used for keys
             # (the same as in Nailgun, for example)

             fuelweb_admin: fuelweb_admin-pool01
             public: public-pool01
             storage: storage-pool01
             management: management-pool01
             private: private-pool01

           l2_network_devices:  # Libvirt bridges. It is *NOT* Nailgun networks
             admin:
               address_pool: fuelweb_admin-pool01
               dhcp: false
               forward:
                 mode: nat
               parent_iface:
                 phys_dev: !os_env BAREMETAL_ADMIN_IFACE, p5p1

             openstack_br:
               vlan_ifaces:
                - 100
                - 101
                - 102
               parent_iface:
                 phys_dev: !os_env BAREMETAL_OS_NETS_IFACE, p4p2

             public:
               address_pool: public-pool01
               dhcp: false
               forward:
                 mode: nat
               parent_iface:
                 l2_net_dev: openstack_br
                 tag: 100

             storage:
               address_pool: storage-pool01
               dhcp: false
               parent_iface:
                 l2_net_dev: openstack_br
                 tag: 101

             management:
               address_pool: management-pool01
               dhcp: false
               parent_iface:
                 l2_net_dev: openstack_br
                 tag: 102

             private:
               address_pool: private-pool01
               dhcp: false

           nodes:
            - name: admin        # Custom name of VM for Fuel admin node
              role: fuel_master  # Fixed role for Fuel master node properties
              params:
                vcpu: !os_env ADMIN_NODE_CPU, 2
                memory: !os_env ADMIN_NODE_MEMORY, 3072
                boot:
                  - hd
                  - cdrom  # for boot from usb - without 'cdrom'
                volumes:
                 - name: system
                   capacity: !os_env ADMIN_NODE_VOLUME_SIZE, 75
                   format: qcow2
                 - name: iso
                   source_image: !os_env ISO_PATH    # if 'source_image' set, then volume capacity is calculated from it's size
                   format: raw
                   device: cdrom   # for boot from usb - 'disk'
                   bus: ide        # for boot from usb - 'usb'
                interfaces:
                 - label: iface0
                   l2_network_device: admin    # Libvirt bridge name. It is *NOT* a Nailgun network
                   interface_model: *interface_model
                network_config:
                  iface0:
                    networks:
                     - fuelweb_admin

              # Slave nodes

            - name: slave-01
              role: fuel_slave
              params:  &rack-01-slave-node-params
                vcpu: !os_env SLAVE_NODE_CPU, 2
                memory: !os_env SLAVE_NODE_MEMORY, 3072
                boot:
                 - network
                 - hd
                volumes:
                 - name: system
                   capacity: !os_env NODE_VOLUME_SIZE, 50
                   format: qcow2
                 - name: cinder
                   capacity: !os_env NODE_VOLUME_SIZE, 50
                   format: qcow2
                 - name: swift
                   capacity: !os_env NODE_VOLUME_SIZE, 50
                   format: qcow2

                # List of node interfaces
                interfaces:
                 - label: iface0
                   l2_network_device: admin      # Libvirt bridge name. It is *NOT* Nailgun networks
                   interface_model: *interface_model

                 - label: iface1
                   l2_network_device: openstack_br      # Libvirt bridge name. It is *NOT* Nailgun networks
                   interface_model: *interface_model

                # How Nailgun/OpenStack networks should assigned for interfaces
                network_config:
                  iface0:
                    networks:
                     - fuelweb_admin  # Nailgun/OpenStack network name
                  iface1:
                    networks:
                     - public
                     - storage
                     - management
                     - private

            - name: slave-02
              role: fuel_slave
              params: *rack-01-slave-node-params
            - name: slave-03
              role: fuel_slave
              params: *rack-01-slave-node-params
