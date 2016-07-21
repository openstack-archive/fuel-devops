#    Copyright 2013 - 2016 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from setuptools import find_packages
from setuptools import setup


setup(
    name='fuel-devops',
    version='3.0.0',
    description='Library for creating and manipulating virtual environments',
    author='Mirantis, Inc.',
    author_email='product@mirantis.com',
    url='http://mirantis.com',
    keywords='devops virtual environment',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(),
    package_data={'devops': ['templates/*.yaml', 'templates/*.yml']},
    scripts=[
        'bin/dos.py',
        'bin/dos-manage.py',
        'bin/dos_check_env.sh',
        'bin/dos_check_system.sh',
        'bin/dos_check_packages.sh',
        'bin/dos_check_db.sh',
    ],
    data_files=[('bin', ['bin/dos_functions.sh'])],
    install_requires=[
        'keystoneauth1>=2.1.0',
        'netaddr>=0.7.12,!=0.7.16',
        'paramiko>=1.16.0,!=2.0.1',
        'Django>=1.8,<1.9',
        'jsonfield',
        'PyYAML>=3.1.0',
        'libvirt-python',
        'tabulate',
        'six>=1.9.0',
        'python-dateutil>=2.4.2',
    ],
    tests_require=[
        'pytest>=2.7.1',
        'pytest-django >= 2.8.0',
        'mock>=1.2',
        'tox>=2.0'
    ],
    extras_require={
        'postgre': ["psycopg2"],
    }
)
