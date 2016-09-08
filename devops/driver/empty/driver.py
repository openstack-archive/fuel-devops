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

from devops.models import driver
from devops.models import network
from devops.models import node
from devops.models import volume


class EmptyDriver(driver.Driver):
    pass


class EmptyInterface(network.Interface):
    pass


class EmptyL2NetworkDevice(network.L2NetworkDevice):
    pass


class EmptyNode(node.Node):
    pass


class EmptyDiskDevice(volume.DiskDevice):
    pass


class EmptyVolume(volume.Volume):
    pass
