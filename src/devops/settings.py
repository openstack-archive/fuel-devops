import os

DRIVER = 'src.devops.driver.libvirt.libvirt_driver.LibvirtDriver'
HOME_DIR = os.environ.get('DEVOPS_HOME') or os.environ.get('APPDATA') or os.environ['HOME']
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