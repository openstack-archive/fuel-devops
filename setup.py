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

import setuptools


setuptools.setup(
    setup_requires=['pbr>=2.0.0'],
    pbr=True,
    scripts=[
        'bin/dos.py',
        'bin/dos-manage.py',
        'bin/dos_check_env.sh',
        'bin/dos_check_system.sh',
        'bin/dos_check_packages.sh',
        'bin/dos_check_db.sh',
    ],)
