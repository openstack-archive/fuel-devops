.. _getstart:

Getting Started
===============

Devops is the library to manage virtual test environments including virtual machines and networks. Management means here making, snapshotting, destroying. You can define as much environments as you need automatically allocating ip addresses to virtual machines avoiding ip clashes. Devops uses Django ORM to save and restore environments.

To start using devops you have to install devops and the most simple way to do that is to use setup.py script.

::

   virtualenv /var/tmp/venv
   source /var/tmp/venv/bin/activate

   git clone git@github.com:Mirantis/devops.git
   cd devops
   python setup.py install

Now it is time to configure it. You can edit default configuration file devops/settings.py or use environment variable DJANGO_SETTINGS_MODULE to define which python module to use as settings module. By default devops uses Postgresql database. Here is the database part of devops/settings.py file.

::

   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.postgresql_psycopg2',
           'NAME': 'postgres',
           'USER': 'postgres',
           'PASSWORD': '',
           'HOST': '',
           'PORT': '',
           'TEST_CHARSET': 'UTF8'
       }
   }

Once database parameters configured it is needed to install corresponding database and configure database itself to make devops applications possible to access to it. For example, to configure Postgresql you need to edit pg_hba.conf file and create configured user and database.

All virtual machines names and virtual networks names will be prepended with environment name avoiding name clashes. As long as different devops applications use not overlaped network ranges and evironments names it is possible to use differnt database for every application. If you are not absolutely sure just use the same database configuration for all devops instances. Once database and devops configured you need to create database schema.

::

   django-admin.py syncdb --settings=custom-settings

It is necessary to note that the path to 'custom-settings' must be in PYTHONPATH.

At this point you are ready to make your first devops application.

::

   import ipaddr
   from devops.manager import Manager
   from devops.models import Environment

   manager = Manager()
   environment = Environment.create(name='myenv')
   node = manager.node_create(name='mynode', environment=environment)

   network_pool = manager.create_network_pool(networks=[ipaddr.IPNetwork('10.0.0.0/16')], prefix=24)
   network = manager.network_create(name='mynet', environment=environment, pool=network_pool)
   manager.interface_create(network=network, node=node)

   volume = manager.volume_create(name='myvol', capacity=10737418240, environment=environment)
   manager.node_attach_volume(node=node, volume=volume)

   environment.define()

This code creates environment 'myenv' with only one VM 'mynode' and attaches 10G qcow2 volume to it. It also creates libvirt network 'mynet' from the range 10.0.0.0/16.
