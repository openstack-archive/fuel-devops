fuel-devops
===========

Django based application providing a sublayer between application and target
environment(all of supported by libvirt currently).

Uses PostgreSQL by default to store data.

This application uses for testing purposes like grouping virtual machines to
environment, booting KVM VM's localy from the ISO image and over the network via
PXE. Snapshot all environemnt and resume them back in single action. Create
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

