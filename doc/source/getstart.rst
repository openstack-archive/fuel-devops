.. _getstart:

Getting Started
===============

Devops is the library to manage virtual test environments including virtual
machines networks and baremetal servers. Management means here making,
snapshotting, destroying. You can define as much environments as you need
automatically allocating ip addresses to virtual machines avoiding ip clashes.
Devops uses Django ORM to save and restore environments.

There are two ways of using devops:

* CLI and yaml template files
* Writing python code on top of devops API


Example of code
***************

.. code-block:: python
   :caption: script.py
   :name: script.py

    from devops.models import Environment


    if __name__ == '__main__':
        env = Environment.create(name='myenv')

        address_pool = env.add_address_pool(
            name='fuelweb_admin-pool01',
            net='10.109.0.0/16:24',
            tag=0)

        group = env.add_group(
            group_name='rack-01',
            driver_name='devops.driver.libvirt.libvirt_driver',
            stp=True,
            hpet=False)

        l2_net_dev = group.add_l2_network_device(
            name='myl2netdev',
            address_pool='fuelweb_admin-pool01',
            dhcp=False,
            forward=dict(mode='nat'))

        net_pool = group.add_network_pool(
            name='fuelweb_admin',
            address_pool='fuelweb_admin-pool01')

        node = group.add_node(
            name='mynode',
            role='default',
            vcpu=2,
            memory=3072)

        interface = node.add_interface(
            label='eth0',
            l2_network_device_name='myl2netdev',
            interface_model='e1000')

        volume = node.add_volume(
            name='myvolume',
            capacity=10,  # 10 GB
            format='qcow2')

        node.add_network_config(
            label='eth0',
            networks=['fuelweb_admin'])

        env.define()


This code creates environment 'myenv' with only one VM 'mynode' and attaches
10G qcow2 volume to it. It also creates libvirt network 'mynet' from the range
10.109.0.0/16.

See more information about API in :ref:`apibasics` section.


Example of yaml template
************************

.. code-block:: yaml
   :caption: template.yaml
   :name: template.yaml

    ---

    template:
        devops_settings:
            env_name: myenv

            address_pools:
                fuelweb_admin-pool01:
                    net: 10.109.0.0/16:24
                    params:
                        tag: 0

            groups:
              - name: rack-01
                driver:
                    name: devops.driver.libvirt.libvirt_driver
                    params:
                        stp: True
                        hpet: False

                network_pools:
                    fuelweb_admin: fuelweb_admin-pool01

                l2_network_devices:
                    myl2netdev:
                        address_pool: fuelweb_admin-pool01
                        dhcp: false
                        forward:
                            mode: nat

                nodes:
                  - name: mynode
                    role: default
                    params:
                        vcpu: 2
                        memory: 3072
                        volumes:
                          - name: myvolume
                            capacity: 10
                            format: qcow2
                        interfaces:
                          - label: eth0
                            l2_network_device: myl2netdev
                            interface_model: e1000
                        network_config:
                            eth0:
                                networks:
                                  - fuelweb_admin


This template describes the same environment as in previous exaple of code.
Use the following CLI command to create it::

    dos.py create-env example.yaml

.. note::

    yaml file should be located in `devops/templates` directory.

See more information about templates in :ref:`templates` section.

See more information about cli commands in :ref:`commandline` section.
