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

from devops.driver.dummy.dummy_driver import DummyDriver as Driver
from devops.models import Interface
from devops.driver.dummy.dummy_driver import \
    DummyL2NetworkDevice as L2NetworkDevice
from devops.driver.dummy.dummy_driver import DummyVolume as Volume
from devops.driver.dummy.dummy_driver import DummyNode as Node

__all__ = [
    'Driver',
    'Interface',
    'L2NetworkDevice',
    'Volume',
    'Node',
]
