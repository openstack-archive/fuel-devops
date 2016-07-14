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

from __future__ import unicode_literals

from unittest import TestCase

from six import with_metaclass

from devops.helpers.metaclasses import SingletonMeta


class TestSingletone(TestCase):
    def test(self):
        class TestClass(with_metaclass(SingletonMeta, object)):
            pass

        tst_obj1 = TestClass()
        tst_obj2 = TestClass()
        self.assertIs(tst_obj1, tst_obj2)
