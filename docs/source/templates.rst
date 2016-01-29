.. _templates:

Using templates
===============



==============================
Using !os_env and !include tags
==============================

- !os_env is used to substitute any part of YAML template with a content
  from a custom environment variable: strings, integers, inline YAML objects
  like lists or dicts.

- !include is used to include a content from a different YAML file. It works
  like YAML aliases but substitute a content from a file instead of alias.

You don't need to use any pre-configured environment variables.
Just choose any name that you like and use it in the template.


Example 1:
----------

# I want to specify the name of a node from the environment variable:
# export MY_SLAVE09_NAME=contrail_slave_node-1

#, and in the template, for node #9:
...
  - name: !os_env MY_SLAVE09_NAME
    role: fuel_slave
...


Example 2:
----------

# I want to override some names of keys in a dictionary, specifying,
# for example, the name of the bond interface from environment variable:

# export MY_FIRST_BOND_IFACE=bond99

...
    network_config:
        !os_env MY_FIRST_BOND_IFACE :
            networks:
               - management
               - public
....


Example 3:
----------

# I want to specify the whole list of slave interfaces from environment
# variable:

# export MY_SLAVE_INTERFACES="\
#   [\
#     {label: eth0, l2_network_device: admin01} ,\
#     {label: eth1, l2_network_device: public01} ,\
#     {label: eth2, l2_network_device: management01} ,\
#     {label: eth3, l2_network_device: storage01} ,\
#     {label: eth4, l2_network_device: storage01} ,\
#   ]"

# , and in the template for required nodes:
...
    - name: slave-05
      role: fuel-slave
      ...
      interfaces: !os_env MY_SLAVE_INTERFACES
....


Example 4:
----------

# You can !include some parts of the yaml file from other yamls like
# interfaces_schema1.yaml, interfaces_schema2.yaml or interfaces_schema3.yaml:

  interfaces:  !include  interfaces_schema2.yaml

# , or specifying it with an environment variable:

export LOAD_MY_INTERFACES='!include ./interfaces_schema2.yaml'

...
   interfaces:  !os_env LOAD_MY_INTERFACES

   # !os_env will get the string that will be parsed as inline yaml,
   # and !include constructor will be executed next, including the dict
   # from './interfaces_schema2.yaml' to the 'interfaces:'.

