DRIVER = 'devops.driver.libvirt.libvirt_driver'
DRIVER_PARAMETERS = {
        'connection_string': 'qemu:///system',
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
