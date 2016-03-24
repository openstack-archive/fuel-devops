#    Copyright 2013 - 2015 Mirantis, Inc.
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

import os

from setuptools import find_packages
from setuptools import setup


setup(
    name='fuel-devops',
    version='2.9.20',
    description='Library for creating and manipulating virtual environments',
    author='Mirantis, Inc.',
    author_email='product@mirantis.com',
    url='http://mirantis.com',
    keywords='devops virtual environment',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(),
    data_files=[
        (os.path.expanduser('~/.devops'), ['devops/log.yaml']),
        (os.path.expanduser('~/.devops/log'), [])],
    scripts=['bin/dos.py'],
    install_requires=[
        'xmlbuilder',
        'ipaddr',
        'paramiko',
        'django<1.7',
        'psycopg2',
        'south',
        'PyYAML',
        'libvirt-python',
        'tabulate',
        'factory_boy>=2.4.1',
        'pytest>=2.7.1',
        'pytest-django >= 2.8.0',
        'mock>=1.0.1',
        'sphinx',
    ]
)
