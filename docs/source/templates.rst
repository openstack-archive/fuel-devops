.. _templates:

YAML fuel-devops templates are used for creating virtual environments
which describe 

Structure of the YAML template for environment creation
=======================================================


YAML template for fuel-devops contains the following objects:

.. code-block::yaml

    # In the 'template' can be stored all data related to the environment.
    # There are stored such keys like 'devops_settings' (for fuel-devops)
    # and 'cluster_template' (for fuel-qa), and some additional keys.
    # For creating virtual environment, fuel-devops use only 'devops_settings'.
    template:
      devops_settings:

        # Each virtual environment in fuel-devops should have an unique name
        env_name: !os_env ENV_NAME

        # Address pools are used for one or more OpenStack/Nailgun networks
        # and for one or more l2_netowork_devices.
        address_pools:

        # Groups are represent virtual 'racks' and can contain one or more
        # node in 'nodes', optional l2_network_devices and optional network_pools.
        groups:
         - name: default

           # Each group have it's own driver used for managing nodes
           # and l2_network_devices. Different drivers can use different parameters
           # that allows to use multi-host, baremetal or mixed environments,
           # allocating some fuel-devops nodes as VM nodes, some as baremetal nodes
           driver:
             name: devops.driver.libvirt.libvirt_driver
             params:

           # Mapping between OpenStack/Nailgun networks and address pools
           network_pools:

           # For libvirt driver, there are described libvirt networks that should
           # be created.
           # For baremetal driver there can be described access details
           # to network appliences and configuration details (not implemented in
           # baremetal driver)
           l2_network_devices:  # Libvirt bridges. It is *NOT* Nailgun networks

           # List of nodes that will be used in the virtual environment.
           # Each node should have an unique name, a role, and list of params that
           # depends on the driver in the group.
           nodes:
            - name: admin        # Custom name of VM for Fuel admin node
              role: fuel_master  # Fixed role for Fuel master node properties
              params:

See detailed examples here:

.. toctree::
   :maxdepth: 2

   templates


===============================
Using !os_env and !include tags
===============================

- !os_env is used to substitute any part of YAML template with a content
  from a custom environment variable: strings, integers, inline YAML objects
  like lists or dicts.

- !include is used to include a content from a different YAML file. It works
  like YAML aliases but substitute a content from a file instead of alias.

You don't need to use any pre-configured environment variables.
Just choose any name that you like and use it in the template.


Example 1:
----------

I want to specify the name of a node from the environment variable:

.. code-block::bash

    export MY_SLAVE09_NAME=contrail_slave_node-1

, and in the template, for node #9:

.. code-block::yaml

    - name: !os_env MY_SLAVE09_NAME
      role: fuel_slave

Example 2:
----------

I want to override some names of keys in a dictionary, specifying,
for example, the name of the bond interface from environment variable:

.. code-block::bash

    export MY_FIRST_BOND_IFACE=bond99

, and in the template, for necessary nodes:

.. code-block::yaml

    network_config:
        !os_env MY_FIRST_BOND_IFACE :
            networks:
               - management
               - public


Example 3:
----------

I want to specify the whole list of slave interfaces from environment
variable:

.. code-block::bash

  export MY_SLAVE_INTERFACES="\
    [\
      {label: eth0, l2_network_device: admin01} ,\
      {label: eth1, l2_network_device: public01} ,\
      {label: eth2, l2_network_device: management01} ,\
      {label: eth3, l2_network_device: storage01} ,\
      {label: eth4, l2_network_device: storage01} ,\
    ]"

, and in the template for required nodes:

.. code-block::yaml

    - name: slave-05
      role: fuel-slave
      ...
      interfaces: !os_env MY_SLAVE_INTERFACES


Example 4:
----------

You can !include some parts of the yaml file from other yamls like
interfaces_schema1.yaml, interfaces_schema2.yaml or interfaces_schema3.yaml:

.. code-block::yaml

  interfaces:  !include  interfaces_schema2.yaml

, or specifying it with an environment variable:

.. code-block::bash

  export LOAD_MY_INTERFACES='!include ./interfaces_schema2.yaml'

, and use this variable in the template:

.. code-block::yaml

   interfaces:  !os_env LOAD_MY_INTERFACES

In this case, !os_env will get the string that will be parsed as inline yaml,
and !include constructor will be executed next.
So the dict from './interfaces_schema2.yaml' will be included to the 'interfaces:'.

