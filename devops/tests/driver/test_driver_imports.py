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

    @staticmethod
    def assert_class_present(mod, mod_path, class_name, expected_class):
        if not hasattr(mod, class_name):
            raise AssertionError(
                '{mod_path}.{class_name} does not exist'
                ''.format(mod_path=mod_path, class_name=class_name))

        klass = getattr(mod, class_name)

        if not issubclass(klass, expected_class):
            raise AssertionError(
                '{mod_path}.{class_name} is not subclass of {expected_class}'
                ''.format(mod_path=mod_path, class_name=class_name,
                          expected_class=expected_class))

    def test_driver_imports(self):
        for _, mod_name, ispkg in pkgutil.iter_modules(driver.__path__):
            if not ispkg:
                continue

            mod_path = 'devops.driver.{}'.format(mod_name)
            mod = importlib.import_module(mod_path)

            self.assert_class_present(mod, mod_path, 'DiskDevice', DiskDevice)
            self.assert_class_present(mod, mod_path, 'Driver', Driver)
            self.assert_class_present(mod, mod_path, 'Interface', Interface)
            self.assert_class_present(
                mod, mod_path, 'L2NetworkDevice', L2NetworkDevice)
            self.assert_class_present(mod, mod_path, 'Node', Node)
            self.assert_class_present(mod, mod_path, 'Volume', Volume)
