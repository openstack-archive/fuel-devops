from setuptools import setup
from setuptools import find_packages

setup(
    name='devops',
    version='2.1',
    description='Library for creating and manipulating virtual environments',
    author='Mirantis, Inc.',
    author_email='product@mirantis.com',
    url='http://mirantis.com',
    keywords='devops virtual environment mirantis',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(),
    scripts=['bin/dos.py'],
    install_requires=[
        'xmlbuilder',
        'ipaddr',
        'paramiko',
        'django>=1.4.3',
        'psycopg2'
    ]
)
