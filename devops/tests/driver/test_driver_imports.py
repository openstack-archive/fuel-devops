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

import importlib
import pkgutil

from django.test import TestCase

from devops import driver
from devops.models import DiskDevice
from devops.models import Driver
from devops.models import Interface
from devops.models import L2NetworkDevice
from devops.models import Node
from devops.models import Volume


class TestDriverImport(TestCase):

    def test_driver_imports(self):
        for importer, modname, ispkg in pkgutil.iter_modules(driver.__path__):
            if not ispkg:
                continue

            if modname == 'ipmi':
                # skip ipmi
                continue

            mod = importlib.import_module('devops.driver.{}'.format(modname))

            assert issubclass(getattr(mod, 'DiskDevice'), DiskDevice)
            assert issubclass(getattr(mod, 'Driver'), Driver)
            assert issubclass(getattr(mod, 'Interface'), Interface)
            assert issubclass(getattr(mod, 'L2NetworkDevice'), L2NetworkDevice)
            assert issubclass(getattr(mod, 'Node'), Node)
            assert issubclass(getattr(mod, 'Volume'), Volume)
