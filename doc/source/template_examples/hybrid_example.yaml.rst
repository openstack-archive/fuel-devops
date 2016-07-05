.. _hybrid_example.yaml:

Hybrid YAML template
====================

This template describes an environment configuration where Fuel admin node
is on a VM on the host, that has connectivity to the baremetal networks
('fuelweb_admin' for PXE provisioning and 'public' for setup NAT from the
baremetal lab to the Internet).

Requirements to use the template with the baremetal lab:

1. If 'parent_iface' is used for any of libvirt l2_network_device,
   'sudo' access on the host is required to automatic connect host's interfaces
   to libvirt virtual networks (linux bridges).

2. Export necessary environment variables:

   .. code-block:: bash

       - ENV_NAME
       - ISO_PATH
       - BAREMETAL_ADMIN_IFACE  # Interface of the host, that has untagged
                                # connectivity to the baremetal PXE network
                                # and other tagged baremetal networks.
                                # It should be in UP state.
                                # Tip: if the 'admin' network should be
                                # connected to an existing bridge on the host,
                                # you can use a veth pair, one iface of
                                # which is included into the bridge, and
                                # another iface is provided in the environment
                                # variable BAREMETAL_ADMIN_IFACE.
       - IPMI_HOST{1..5}, IPMI_USER, IPMI_PASSWORD  # Access credentials
                                                    # to IPMI nodes
3. Configure MACs for *all* interfaces. In this template, order of the
   interfaces doesn't matter, because mapping OpenStack networks on node
   interfaces will be done using specified MAC addresses. So if a server
   has 4 network interfaces, but you planned to use only 2 interfaces for
   OpenStack networks, you can configure here only these 2 interfaces.

4. Use this template to create the environment:
   - From command line:

     .. code-block:: bash

         $ dos.py create-env ./path/to/hybrid_template.yaml

   - For already existing system tests (TEST_GROUP='smoke_neutron' for example)
     (requires fuel-qa branch > stable/mitaka, with support for fuel-devops3.0)

     .. code-block:: bash

         $ export DEVOPS_SETTINGS_TEMPLATE=./path/to/hybrid_template.yaml
         $ sh -x "utils/jenkins/system_tests.sh" \
              -t test \
              -w "${WORKSPACE}" \
              -V "${VENV_PATH}" \
              -j "${JOB_NAME}" \
              -o --group="${TEST_GROUP}" \
              -i "${ISO_PATH}"

   - For fuel-qa/fuel_tests (pytest-based):
     - In the test class, initialize self.config_file=./path/to/hybrid_template.yaml
     - Use @pytest.mark.need_ready_cluster for test case methods to load the config and
       prepare the environment.


Additional details about this template:

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
 - 'public' l2_network_device in the libvirt group is used for providing NAT
   from baremetal tagged public network to the Internet, and for access to
   public IPs on the baremetal nodes directly from system tests.
 - Despite the fact that there is used two node groups, all baremetal nodes
   actually are connected to the PXE admin network of the first node group
   and will be bootstrapped as the nodes of the first node group. Second
   node group will not be used with this config, because it requires another
   network setup and manual Fuel configuration for additional interfaces.


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
              vlan_start: 0
              ip_reserved:
                gateway: +1
                l2_network_device: +1  # l2_network_device will get this IP address
              ip_ranges:
                default: [+2, -2]     # admin IP range for 'default' nodegroup name

          public-pool01:
            net: *pool_default
            params:
              vlan_start: 200
              ip_reserved:
                gateway: +1
                l2_network_device: +1  # l2_network_device will get this IP address
              ip_ranges:
                default: [+2, +127]  # public IP range for 'default' nodegroup name
                floating: [+128, -2]

          storage-pool01:
            net: *pool_default
            params:
              vlan_start: 201

          management-pool01:
            net: *pool_default
            params:
              vlan_start: 202

          private-pool01:
            net: *pool_default
            params:
              vlan_start: 960
              vlan_end: 1000

          fuelweb_admin-pool02:
            net: *pool_default
            params:
              vlan_start: 0

          public-pool02:
            net: *pool_default
            params:
              vlan_start: 200

          storage-pool02:
            net: *pool_default
            params:
              vlan_start: 201

          management-pool02:
            net: *pool_default
            params:
              vlan_start: 202

          private-pool02:
            net: *pool_default
            params:
              vlan_start: 960

        groups:
         - name: default
           driver:
             name: devops.driver.libvirt
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
                 # If the 'admin' network should be connected to an existing
                 # bridge instead of dedicated interface, use a veth pair.
                 phys_dev: !os_env BAREMETAL_ADMIN_IFACE, eth1
               vlan_ifaces:
                - 200

             public:
               address_pool: public-pool01
               dhcp: false
               forward:
                 mode: nat
               parent_iface:
                 l2_net_dev: admin
                 tag: 200

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
                  iface1:
                    networks:
                     - fuelweb_admin

         - name: baremetal-rack01
           driver:
             name: devops.driver.baremetal
              # Slave nodes

           network_pools:  # Address pools for OpenStack networks.
             # Actual names should be used for keys
             # (the same as in Nailgun, for example)

             fuelweb_admin: fuelweb_admin-pool02
             public: public-pool02
             storage: storage-pool02
             management: management-pool02
             private: private-pool02

           nodes:
            - name: slave-01  # Custom name of baremetal for Fuel slave node
              role: fuel_slave  # Fixed role for Fuel master node properties
              params:
                ipmi_user: !os_env IPMI_USER
                ipmi_password: !os_env IPMI_PASSWORD
                ipmi_previlegies: OPERATOR
                ipmi_host: !os_env IPMI_HOST1
                ipmi_lan_interface: lanplus
                ipmi_port: 623

                # so, interfaces can be turn on in one or in a different switches.
                interfaces:
                 - label: iface1
                   mac_address: xx:xx:xx:xx:xx:xx
                 - label: iface2
                   mac_address: xx:xx:xx:xx:xx:xx
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
                ipmi_user: !os_env IPMI_USER
                ipmi_password: !os_env IPMI_PASSWORD
                ipmi_previlegies: OPERATOR
                ipmi_host: !os_env IPMI_HOST2
                ipmi_lan_interface: lanplus
                ipmi_port: 623

                # so, interfaces can be turn on in one or in a different switches.
                interfaces:
                 - label: iface1
                   mac_address: xx:xx:xx:xx:xx:xx
                 - label: iface2
                   mac_address: xx:xx:xx:xx:xx:xx
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
                ipmi_user: !os_env IPMI_USER
                ipmi_password: !os_env IPMI_PASSWORD
                ipmi_previlegies: OPERATOR
                ipmi_host: !os_env IPMI_HOST3
                ipmi_lan_interface: lanplus
                ipmi_port: 623

                # so, interfaces can be turn on in one or in a different switches.
                interfaces:
                 - label: iface1
                   mac_address: xx:xx:xx:xx:xx:xx
                 - label: iface2
                   mac_address: xx:xx:xx:xx:xx:xx
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
                ipmi_user: !os_env IPMI_USER
                ipmi_password: !os_env IPMI_PASSWORD
                ipmi_previlegies: OPERATOR
                ipmi_host: !os_env IPMI_HOST4
                ipmi_lan_interface: lanplus
                ipmi_port: 623

                # so, interfaces can be turn on in one or in a different switches.
                interfaces:
                 - label: iface1
                   mac_address: xx:xx:xx:xx:xx:xx
                 - label: iface3
                   mac_address: xx:xx:xx:xx:xx:xx
                 - label: iface4
                   mac_address: xx:xx:xx:xx:xx:xx
                network_config:
                  iface1:
                    networks:
                     - fuelweb_admin  ## OpenStack network, NOT switch name
                     - public  ## OpenStack network, NOT switch name
                  iface3:
                    networks:
                     - storage  ## OpenStack network, NOT switch name
                     - management  ## OpenStack network, NOT switch name
                     - private  ## OpenStack network, NOT switch name

            - name: slave-05  # Custom name of baremetal for Fuel slave node
              role: fuel_slave  # Fixed role for Fuel master node properties
              params:
                ipmi_user: !os_env IPMI_USER
                ipmi_password: !os_env IPMI_PASSWORD
                ipmi_previlegies: OPERATOR
                ipmi_host: !os_env IPMI_HOST5
                ipmi_lan_interface: lanplus
                ipmi_port: 623

                # so, interfaces can be turn on in one or in a different switches.
                interfaces:
                 - label: iface1
                   mac_address: xx:xx:xx:xx:xx:xx
                 - label: iface3
                   mac_address: xx:xx:xx:xx:xx:xx
                 - label: iface4
                   mac_address: xx:xx:xx:xx:xx:xx
                network_config:
                  iface1:
                    networks:
                     - fuelweb_admin  ## OpenStack network, NOT switch name
                     - public  ## OpenStack network, NOT switch name
                  iface3:
                    networks:
                     - storage  ## OpenStack network, NOT switch name
                     - management  ## OpenStack network, NOT switch name
                     - private  ## OpenStack network, NOT switch name
