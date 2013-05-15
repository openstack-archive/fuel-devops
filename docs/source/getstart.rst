.. _getstart:

Getting Started
===============

Devops is the library to manage virtual test environments including virtual machines and networks. Management means here making, snapshotting, destroying. You can define as much environments as you need automatically allocating ip addresses to virtual machines avoiding ip clashes. Devops uses Django ORM to save and restore environments and all devops installations on certain system must use the same database settings. It is needed to avoid name and IP overlaps.

To start using devops you have to install devops. The most simple way to do that is to use setup.py script.

::

   virtualenv /var/tmp/venv-devops
   source /var/tmp/venv-devops/bin/activate

   git clone git@github.com:Mirantis/devops.git
   cd devops
   python setup.py install

Now it is the time to configure it. You can edit default configuration file devops/settings.py or use environment variable DJANGO_SETTINGS_MODULE to define which python module to use as settings module. By default devops uses Postgresql database. As already mentioned above every devops application must use the same database configuration.

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

So you need install corresponding database and configure it to make devops applications possible to access to it. For example, to configure Postgresql you need to edit pg_hba.conf file (Ubuntu: /etc/posgresql/9.1/main/pg_hba.conf, Centos: /var/lib/pgsql/data/pg_hba.conf) and to change postgres password to what you want it to be.

Once database and devops configured you need to create database schema.

::

   django-admin.py syncdb --settings devops.settings

At this point you are ready to make your first devops application.

