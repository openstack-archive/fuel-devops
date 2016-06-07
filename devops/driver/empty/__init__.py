#    Copyright 2016 Mirantis, Inc.
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

from devops.driver.empty.driver import EmptyDriver as Driver
from devops.driver.empty.driver import EmptyInterface as Interface
from devops.driver.empty.driver import EmptyL2NetworkDevice as L2NetworkDevice
from devops.driver.empty.driver import EmptyVolume as Volume
from devops.driver.empty.driver import EmptyNode as Node

__all__ = [
    'Driver',
    'Interface',
    'L2NetworkDevice',
    'Volume',
    'Node',
]
