.. _cloudinit_example.yaml:

YAML template for cloud-init nodes
==================================

This template can be used for nodes that are started from Ubuntu
cloud images (or CentOS, with necessary changes in cloudinit_user_data).

The following set of cloudinit_user_data and cloudinit_meta_data is an
example, change it for your purposes.


.. code-block:: yaml

    ---
    aliases:
      dynamic_addresses_pool:
        - &pool_default !os_env POOL_DEFAULT, 10.10.0.0/16:24

      default_interface_model:
        - &interface_model !os_env INTERFACE_MODEL, e1000

    template:
      devops_settings:
        env_name: !os_env ENV_NAME

        address_pools:
          public-pool01:
            net: *pool_default
            params:
              vlan_start: 1210
              ip_reserved:
                gateway: +1
                l2_network_device: +1
              ip_ranges:
                dhcp: [+128, -32]
                rack-01: [+2, +127]
          private-pool01:
            net: *pool_default
          storage-pool01:
            net: *pool_default
          management-pool01:
            net: *pool_default

        groups:
          - name: default
            driver:
              name: devops.driver.libvirt
              params:
                connection_string: !os_env CONNECTION_STRING, qemu:///system
                storage_pool_name: !os_env STORAGE_POOL_NAME, default
                stp: False
                hpet: False
                use_host_cpu: !os_env DRIVER_USE_HOST_CPU, true

            network_pools:
              public: public-pool01
              private: private-pool01
              storage: storage-pool01
              management: management-pool01

            l2_network_devices:
              public:
                address_pool: public-pool01
                dhcp: true
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
              - name: node-1
                role: k8s
                params: &rack-01-node-params
                  vcpu: !os_env SLAVE_NODE_CPU, 2
                  memory: !os_env SLAVE_NODE_MEMORY, 2048
                  boot:
                    - hd
                  cloud_init_volume_name: iso
                  cloud_init_iface_up: enp0s3
                  volumes:
                    - name: system
                      capacity: !os_env NODE_VOLUME_SIZE, 50
                      source_image: !os_env CLOUD_IMAGE_PATH  # https://cloud-images.ubuntu.com/xenial/current/xenial-server-cloudimg-amd64-disk1.img
                      format: qcow2
                    - name: iso  # Volume with name 'iso' will be used
                                 # for store image with cloud-init metadata.
                      capacity: 1
                      format: raw
                      device: cdrom
                      bus: ide
                      cloudinit_meta_data: |
                        # All the data below will be stored as a string object
                        instance-id: iid-local1
                        local-hostname: {hostname}
                        network-interfaces: |
                         auto {interface_name}
                         iface {interface_name} inet static
                         address {address}
                         network {network}
                         netmask {netmask}
                         gateway {gateway}
                         dns-nameservers 8.8.8.8

                      cloudinit_user_data: |
                        #cloud-config, see http://cloudinit.readthedocs.io/en/latest/topics/examples.html
                        # All the data below will be stored as a string object

                        ssh_pwauth: True
                        users:
                         - name: vagrant
                           sudo: ALL=(ALL) NOPASSWD:ALL
                           shell: /bin/bash
                        chpasswd:
                         list: |
                          vagrant:vagrant
                         expire: False

                        bootcmd:
                         # Block access to SSH while node is preparing
                         - cloud-init-per once sudo iptables -A INPUT -p tcp --dport 22 -j DROP
                        runcmd:
                         # Prepare network connection
                         - sudo ifup {interface_name}
                         - sudo route add default gw {gateway} {interface_name}

                         # Prepare necessary packages on the node
                         - sudo apt-get update
                         - sudo apt-get upgrade -y
                         - sudo apt-get install -y git python-setuptools python-dev python-pip gcc libssl-dev libffi-dev vim software-properties-common
                         - sudo apt-get autoremove -y
                         - sudo pip install -U setuptools pip
                         - sudo pip install 'cryptography>=1.3.2'
                         - sudo pip install 'cffi>=1.6.0'

                         # Node is ready, allow SSH access
                         - sudo iptables -D INPUT -p tcp --dport 22 -j DROP

                  interfaces:
                    - label: enp0s3
                      l2_network_device: public
                      interface_model: *interface_model
                    - label: enp0s4
                      l2_network_device: private
                      interface_model: *interface_model
                    - label: enp0s5
                      l2_network_device: storage
                      interface_model: *interface_model
                    - label: enp0s6
                      l2_network_device: management
                      interface_model: *interface_model
                  network_config:
                    enp0s3:
                      networks:
                        - public
                    enp0s4:
                      networks:
                        - private
                    enp0s5:
                      networks:
                        - storage
                    enp0s6:
                      networks:
                        - management

              - name: node-2
                role: k8s
                params: *rack-01-node-params

              - name: node-3
                role: k8s
                params: *rack-01-node-params
