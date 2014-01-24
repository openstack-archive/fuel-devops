fuel-devops
===========

Fuel-Devops is a sublayer between application and target environment(all of
supported by libvirt currently).

This application is used for testing purposes like grouping virtual machines to
environments, booting KVM VM's locally from the ISO image and over the network via
PXE, creating, snapshotting and resuming back the whole environment in single
action, create virtual machines with multiple NICs, multiple hard drives and many
other customizations with a few lines of code in system tests.

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
 * python-south

Installation
------------
	django-admin.py syncdb --settings=devops.settings
	django-admin.py migrate devops --settings=devops.settings
