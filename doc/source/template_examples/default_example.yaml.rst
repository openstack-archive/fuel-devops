.. _default_example.yaml:

Default YAML template
=====================

This template describes a standard environment configuration that is used
by most of fuel-qa system tests:

 - All nodes (except Fuel master node) have 5 network interfaces and 3 disks;
 - Untagged 'fuelweb_admin', 'public', 'management', 'storage' and 'private'
   OpenStack networks are mapped on 5 libvirt networks (l2_network_devices);
 - Template uses the following required environment variables:
   * ENV_NAME: environment name
   * ISO_PATH: full path to the Fuel ISO
 - Template uses the following optional environment variables:
   * ADMIN_NODE_CPU: number of CPUs on Fuel master node
   * ADMIN_NODE_MEMORY: amount of memory for Fuel master node
   * ADMIN_NODE_VOLUME_SIZE: size of the 'system' disk for Fuel master node
   * SLAVE_NODE_CPU: number of CPUs on slave nodes
   * SLAVE_NODE_MEMORY: amount of memory for slave nodes
   * NODE_VOLUME_SIZE: size of all three disks for slave nodes
   * POOL_DEFAULT: address pool in format <basic_cidr>:<prefix>
   * CONNECTION_STRING: Libvirt connection string
   * STORAGE_POOL_NAME: Pool name for images of VMs
   * DRIVER_USE_HOST_CPU: CPU type used by VMs can be copied from the host

.. code-block:: yaml

    ---
    aliases:

      dynamic_address_pool:
       - &pool_default !os_env POOL_DEFAULT, 10.109.0.0/16:24

    template:
      devops_settings:
        env_name: !os_env ENV_NAME

        address_pools:
        # Network pools used by the environment
          fuelweb_admin-pool01:
            net: *pool_default
          public-pool01:
            net: *pool_default
          storage-pool01:
            net: *pool_default
          management-pool01:
            net: *pool_default
          private-pool01:
            net: *pool_default

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

             public:
               address_pool: public-pool01
               dhcp: false
               forward:
                 mode: nat

             storage:
               address_pool: storage-pool01
               dhcp: false

             management:
               address_pool: management-pool01
               dhcp: false

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
                 - label: iface1
                   l2_network_device: admin    # Libvirt bridge name. It is *NOT* a Nailgun network
                network_config:
                  iface1:
                    networks:
                     - fuelweb_admin

            - name: slave-01
              role: fuel_slave

              # Alias 'rack-01-slave-node-params' will be used for
              # putting the same 'params' to the next slave nodes.
              params: &rack-01-slave-node-params

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

                interfaces:
                 - label: iface1
                   l2_network_device: admin      # Libvirt bridge name. It is *NOT* Nailgun networks
                 - label: iface2
                   l2_network_device: public
                 - label: iface3
                   l2_network_device: storage
                 - label: iface4
                   l2_network_device: management
                 - label: iface5
                   l2_network_device: private

                network_config:
                  iface1:
                    networks:
                     - fuelweb_admin
                  iface2:
                    networks:
                     - public
                  iface3:
                    networks:
                     - storage
                  iface4:
                    networks:
                     - management
                  iface5:
                    networks:
                     - private

            - name: slave-02
              role: fuel_slave
              params: *rack-01-slave-node-params
            - name: slave-03
              role: fuel_slave
              params: *rack-01-slave-node-params
            - name: slave-04
              role: fuel_slave
              params: *rack-01-slave-node-params
            - name: slave-05
              role: fuel_slave
              params: *rack-01-slave-node-params
            - name: slave-06
              role: fuel_slave
              params: *rack-01-slave-node-params
            - name: slave-07
              role: fuel_slave
              params: *rack-01-slave-node-params
            - name: slave-08
              role: fuel_slave
              params: *rack-01-slave-node-params
            - name: slave-09
              role: fuel_slave
              params: *rack-01-slave-node-params
