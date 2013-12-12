fuel-devops
===========

Fuel-Devops is a sublayer between application and target environment(all of
supported by libvirt currently).

This application is used for testing purposes like grouping virtual machines to
environments, booting KVM VM's localy from the ISO image and over the network via
PXE, snapshot the whole environemnt and resume it back in single action, create
virtual machines with multiple NICs, multiple hard drives and many other
customizations with a few lines of code in system tests.

Dependencies
------------
 * postgresql
 * python-psycopg2
 * python-ipaddr
 * python-libvirt
 * python-virtualenv
 * python-ipaddr
 * python-paramiko
 * python-django (>= 1.4)
 * python-xmlbuilder

