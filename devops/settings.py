from os import environ

DRIVER = 'devops.driver.libvirt.libvirt_driver'
DRIVER_PARAMETERS = {
    'connection_string': environ.get('CONNECTION_STRING', 'qemu:///system'),
    'storage_pool_name': environ.get('STORAGE_POOL_NAME', 'default'),
}

INSTALLED_APPS = ['devops']

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

SECRET_KEY = 'dummykey'

VNC_PASSWORD = environ.get('VNC_PASSWORD', None)
