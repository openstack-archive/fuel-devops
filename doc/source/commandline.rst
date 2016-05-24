.. _commandline:

Command line interface
======================

Usage
*****

Run `dos.py -h` to see full list of supported actions::

    ...
    Operation commands:
        list                Show virtual environments
        show                Show VMs in environment
        erase               Delete environment
        start               Start VMs
        destroy             Destroy(stop) VMs
        suspend             Suspend VMs
        resume              Resume VMs
        revert              Apply snapshot to environment
        snapshot            Make environment snapshot
        sync                Synchronization environment and devops
        snapshot-list       Show snapshots in environment
        snapshot-delete     Delete snapshot from environment
        net-list            Show networks in environment
        time-sync           Sync time on all env nodes
        revert-resume       Revert, resume, sync time on VMs
        version             Show devops version
        create              Create a new environment (DEPRECATED)
        create-env          Create a new environment
        slave-add           Add a node
        slave-change        Change node VCPU and memory config
        slave-remove        Remove node from environment
        admin-setup         Setup admin node
        admin-setup-centos7
                            Setup CentOS 7 based admin node
        admin-change        Change admin node VCPU and memory config
        node-start          Start node in environment
        node-destroy        Destroy (power off) node in environment
        node-reset          Reset (restart) node in environment

Use `dos.py -h` to see help for specific command::

    $ dos.py create-env --help
    usage: dos.py create-env [-h] env_config_name

    Create an environment from a template file

    positional arguments:
      env_config_name  environment template name

    optional arguments:
      -h, --help       show this help message and exit


CLI Basics
**********

This tutorial shows basic cli actions.

Create environment
------------------

Yaml template file is required for creation of environment using cli. It
contains information about all components of environment::

    dos.py create-env /path/to/template.yaml

Actions
-------

After creation the environment will be available in the list of existing
evironments::

    $ dos.py list
    NAME
    ------
    myenv

Also the list of nodes can be printed::

    $ dos.py show myenv
      VNC  NODE-NAME
    -----  -----------
       -1  admin

There is a list of comands which manipulate all nodes inside selected
environment::

    dos.py start myenv
    dos.py suspend myenv
    dos.py resume myenv
    dos.py destroy myenv

Also there are comands which manipulate selected node::

    dos.py node-start myenv --node-name admin
    dos.py node-reset myenv --node-name admin
    dos.py node-destroy myenv --node-name admin

Remove environment
------------------

Use the following command to remove environmet and all elements it contains::

    dos.py erase myenv
