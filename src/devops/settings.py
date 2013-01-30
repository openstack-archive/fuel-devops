import os

DRIVER = 'src.devops.driver.libvirt.libvirt_driver.LibvirtDriver'
HOME_DIR = os.environ.get('DEVOPS_HOME') or os.environ.get('APPDATA') or os.environ['HOME']
INSTALLED_APPS = ['devops']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.abspath(os.path.join(HOME_DIR, 'devops.db')),
        'TIMEOUT': 60,
    }
}