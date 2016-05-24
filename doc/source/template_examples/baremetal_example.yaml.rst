.. _baremetal_example.yaml:

Baremetal YAML template
=======================

This template describes an environment configuration where Fuel admin node
is on a VM on the host, that has connectivity to the baremetal networks
('fuelweb_admin' for PXE provisioning and 'public' for setup NAT from the
baremetal lab to the Internet.

This template, with correct IPMI credentials and sudo access on the host
for `brctl` command, can be used for run most of fuel-qa system tests on
a baremetal lab (requires the [1] merged to fuel-qa).

 - Fuel master node is on a separate node group because different fuel-devops
   drivers are used for Fuel master node and for baremetal nodes;
 - All OpenStack networks except fuelweb_admin are tagged;
 - All interfaces on baremetal nodes that will be assigned for OpenStack
   networks should be configured with the correct MAC addresses. It is required
   for automatic mapping OpenStack networks on proper node interfaces during
   system tests;
 - 'l2_network_devices' object is not required for the baremetal node group;
 - By default, 'eth1' is added to the libvirt bridge of the 'admin'
   l2_network_device to get connectivity to the baremetal networks connected
   to this host's interface;
 - 'public' l2_network_device is used for providing NAT from baremetal public
   network to the Internet, and for access to the public IPs from system
   tests;

[1] https://review.openstack.org/#/c/292977/


.. code-block:: yaml

    ---
    aliases:

      dynamic_address_pool:
       - &pool_default !os_env POOL_DEFAULT, 10.109.0.0/16:24

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
                l2_network_device: +1  # l2_network_device will get this IP address
              ip_ranges:
                default: [+2, -2]     # admin IP range for 'default' nodegroup name

          public-pool01:
            net: *pool_default
            params:
              vlan_start: 100
              ip_reserved:
                gateway: +1
                l2_network_device: +1  # l2_network_device will get this IP address
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
              vlan_start: 960
              vlan_end: 1000

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
                 phys_dev: !os_env BAREMETAL_ADMIN_IFACE, eth1
               vlan_ifaces:
                - 100

             public:
               address_pool: public-pool01
               dhcp: false
               forward:
                 mode: nat
               parent_iface:
                 l2_net_dev: admin
                 tag: 100

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
                   interface_model: *interface_model
                network_config:
                  iface1
                    networks:
                     - fuelweb_admin

        groups:
         - name: baremetal-rack-01
           driver:
             name: devops.driver.baremetal.ipmi_driver
              # Slave nodes

           network_pools:  # Address pools for OpenStack networks.
             # Actual names should be used for keys
             # (the same as in Nailgun, for example)

             fuelweb_admin: fuelweb_admin-pool01
             public: public-pool01
             storage: storage-pool01
             management: management-pool01
             private: private-pool01

           nodes:
            - name: slave-01  # Custom name of baremetal for Fuel slave node
              role: fuel_slave  # Fixed role for Fuel master node properties
              params:
                ipmi_user: username1
                ipmi_password: password1
                ipmi_previlegies: OPERATOR
                ipmi_host: ipmi1.test.local
                ipmi_lan_interface: lanplus
                ipmi_port: 623
                impi_cmd: ipmitool

                # so, interfaces can be turn on in one or in a different switches.
                interfaces:
                 - label: iface1
                   mac: aa:bb:cc:dd:ee:11
                 - label: iface2
                   mac: aa:bb:cc:dd:ee:12
                network_config:
                  iface1:
                    networks:
                     - fuelweb_admin  ## OpenStack network, NOT switch name
                     - public  ## OpenStack network, NOT switch name
                  iface2:
                    networks:
                     - storage  ## OpenStack network, NOT switch name
                     - management  ## OpenStack network, NOT switch name
                     - private  ## OpenStack network, NOT switch name

            - name: slave-02  # Custom name of baremetal for Fuel slave node
              role: fuel_slave  # Fixed role for Fuel master node properties
              params:
                ipmi_user: username2
                ipmi_password: password2
                ipmi_previlegies: OPERATOR
                ipmi_host: ipmi2.test.local
                ipmi_lan_interface: lanplus
                ipmi_port: 623
                impi_cmd: ipmitool

                # so, interfaces can be turn on in one or in a different switches.
                interfaces:
                 - label: iface1
                   mac: aa:bb:cc:dd:ee:21
                 - label: iface2
                   mac: aa:bb:cc:dd:ee:22
                network_config:
                  iface1:
                    networks:
                     - fuelweb_admin  ## OpenStack network, NOT switch name
                     - public  ## OpenStack network, NOT switch name
                  iface2:
                    networks:
                     - storage  ## OpenStack network, NOT switch name
                     - management  ## OpenStack network, NOT switch name
                     - private  ## OpenStack network, NOT switch name

            - name: slave-03  # Custom name of baremetal for Fuel slave node
              role: fuel_slave  # Fixed role for Fuel master node properties
              params:
                ipmi_user: username3
                ipmi_password: password3
                ipmi_previlegies: OPERATOR
                ipmi_host: ipmi3.test.local
                ipmi_lan_interface: lanplus
                ipmi_port: 623
                impi_cmd: ipmitool

                # so, interfaces can be turn on in one or in a different switches.
                interfaces:
                 - label: iface1
                   mac: aa:bb:cc:dd:ee:31
                 - label: iface2
                   mac: aa:bb:cc:dd:ee:32
                network_config:
                  iface1:
                    networks:
                     - fuelweb_admin  ## OpenStack network, NOT switch name
                     - public  ## OpenStack network, NOT switch name
                  iface2:
                    networks:
                     - storage  ## OpenStack network, NOT switch name
                     - management  ## OpenStack network, NOT switch name
                     - private  ## OpenStack network, NOT switch name

            - name: slave-04  # Custom name of baremetal for Fuel slave node
              role: fuel_slave  # Fixed role for Fuel master node properties
              params:
                ipmi_user: username4
                ipmi_password: password4
                ipmi_previlegies: OPERATOR
                ipmi_host: ipmi4.test.local
                ipmi_lan_interface: lanplus
                ipmi_port: 623
                impi_cmd: ipmitool

                # so, interfaces can be turn on in one or in a different switches.
                interfaces:
                 - label: iface1
                   mac: aa:bb:cc:dd:ee:41
                 - label: iface2
                   mac: aa:bb:cc:dd:ee:42
                 - label: iface3
                   mac: aa:bb:cc:dd:ee:43
                 - label: iface4
                   mac: aa:bb:cc:dd:ee:44
                network_config:
                  iface1:
                    networks:
                     - fuelweb_admin  ## OpenStack network, NOT switch name
                  iface2:
                     - public  ## OpenStack network, NOT switch name
                  iface3:
                    networks:
                     - storage  ## OpenStack network, NOT switch name
                     - management  ## OpenStack network, NOT switch name
                  iface4:
                     - private  ## OpenStack network, NOT switch name

            - name: slave-05  # Custom name of baremetal for Fuel slave node
              role: fuel_slave  # Fixed role for Fuel master node properties
              params:
                ipmi_user: username5
                ipmi_password: password5
                ipmi_previlegies: OPERATOR
                ipmi_host: ipmi5.test.local
                ipmi_lan_interface: lanplus
                ipmi_port: 623
                impi_cmd: ipmitool

                # so, interfaces can be turn on in one or in a different switches.
                interfaces:
                 - label: iface1
                   mac: aa:bb:cc:dd:ee:51
                 - label: iface2
                   mac: aa:bb:cc:dd:ee:52
                 - label: iface3
                   mac: aa:bb:cc:dd:ee:53
                 - label: iface4
                   mac: aa:bb:cc:dd:ee:54
                network_config:
                  iface1:
                    networks:
                     - fuelweb_admin  ## OpenStack network, NOT switch name
                  iface2:
                     - public  ## OpenStack network, NOT switch name
                  iface3:
                    networks:
                     - storage  ## OpenStack network, NOT switch name
                     - management  ## OpenStack network, NOT switch name
                  iface4:
                     - private  ## OpenStack network, NOT switch name
