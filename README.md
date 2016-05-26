fuel-devops
===========

Fuel-Devops is a sublayer between application and target environment(all of
supported by libvirt currently).

This application is used for testing purposes like grouping virtual machines to
environments, booting KVM VM's locally from the ISO image and over the network via
PXE, creating, snapshotting and resuming back the whole environment in single
action, create virtual machines with multiple NICs, multiple hard drives and many
other customizations with a few lines of code in system tests.

Installation
-------------
The installation procedure can be implemented via PyPI in Python virtual environment (suppose you are using Ubuntu 12.04, Ubuntu 14.04 or Ubuntu 16.04):

Before using it, please install the following required dependencies:

    sudo apt-get install git \
    postgresql \
    postgresql-server-dev-all \
    libyaml-dev \
    libffi-dev \
    python-dev \
    python-libvirt \
    python-pip \
    qemu-kvm \
    qemu-utils \
    libvirt-bin \
    libvirt-dev \
    ubuntu-vm-builder \
    bridge-utils

    sudo apt-get update && sudo apt-get upgrade -y

Install packages needed for building python eggs

    sudo apt-get install python-virtualenv libpq-dev libgmp-dev

In case you are using Ubuntu 12.04 let’s update pip and virtualenv, otherwise you can skip this step

    sudo pip install pip virtualenv --upgrade
    hash -r

Create virtualenv for the devops project

    virtualenv --system-site-packages <path>/fuel-devops-venv

Note

Activate virtualenv and install devops package using PyPI.

    source  <path>/fuel-devops-venv/bin/activate
    pip install git+https://github.com/openstack/fuel-devops.git@<version> --upgrade

Configuration
=============

Basically fuel-devops requires that the following system-wide settings are configured:

* Default libvirt storage pool is active (called ‘default’)
* Current user must have permission to run KVM VMs with libvirt
* PostgreSQL server running with appropriate grants and schema for devops
* [Optional] Nested Paging is enabled
* [Optional] Network filter for host bridges should be disabled: [http://wiki.libvirt.org/page/Net.bridge-nf-call_and_sysctl.conf](http://wiki.libvirt.org/page/Net.bridge-nf-call_and_sysctl.conf).

Usage
=====
Run dos.py -h to see full list of supported actions

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
    create              Create a new environment
    slave-add           Add a node
    slave-change        Change node VCPU and memory config
    slave-remove        Remove node from environment
    admin-setup         Setup admin node
    admin-change        Change admin node VCPU and memory config
    node-start          Start node in environment
    node-destroy        Destroy (power off) node in environment
    node-reset          Reset (restart) node in environment

Use dos.py <command> -h to see help for specific command

    positional arguments:
    ENV_NAME              environment name

    optional arguments:
    -h, --help            show this help message and exit
    --vcpu VCPU_COUNT     Set node VCPU count
    --node-count NODE_COUNT, -C NODE_COUNT
                        How many nodes will be created
    --ram RAM_SIZE        Set node RAM size
    --net-pool NET_POOL, -P NET_POOL
                        Set ip network pool (cidr)
    --iso-path ISO_PATH, -I ISO_PATH
                        Set Fuel ISO path
    ...

Testing
==========
There are next test targets that can be run to validate the code.

    tox -e pep8   - style guidelines enforcement
    tox -e pylint - static analisys of code quality
    tox -e py27   - unit and integration testing on Python 2.7 (if available)
    tox -e py34   - unit and integration testing on Python 3.4 (if available)
    tox -e py35   - unit and integration testing on Python 3.5 (if available)
    tox -e cover  - tests coverage check
    tox -e docs   - documentation consistency check

