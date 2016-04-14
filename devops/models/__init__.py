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

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "devops.settings")

from devops.models.driver import Driver
from devops.models.environment import Environment
from devops.models.group import Group
from devops.models.network import Address
from devops.models.network import Interface
from devops.models.network import AddressPool
from devops.models.network import NetworkPool
from devops.models.network import L2NetworkDevice
from devops.models.node import Node
from devops.models.volume import Volume
from devops.models.volume import DiskDevice

__all__ = ['Driver', 'Environment', 'Group', 'Address', 'Interface',
           'AddressPool', 'NetworkPool', 'L2NetworkDevice', 'Node',
           'Volume', 'DiskDevice']
