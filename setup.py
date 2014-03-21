#    Copyright 2014 Mirantis, Inc.
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

from setuptools import setup
from setuptools import find_packages

setup(
    name='devops',
    version='2.2',
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
        'psycopg2',
        'south',
        'mock'
    ]
)
