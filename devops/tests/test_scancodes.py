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

import unittest
from devops.helpers import scancodes


class TestScancodes(unittest.TestCase):
    def test_abc(self):
        codes = scancodes.from_string('abc')
        self.assertEqual([(0x1e,), (0x30,), (0x2e,)], codes)

    def test_ABC(self):
        codes = scancodes.from_string('ABC')
        self.assertEqual([(0x2a, 0x1e), (0x2a, 0x30), (0x2a, 0x2e)], codes)

    def test_specials(self):
        codes = scancodes.from_string('<Esc>a<Up>b')
        self.assertEqual([(0x01,), (0x1e,), (0x48,), (0x30,)], codes)

    def test_newlines_are_ignored(self):
        codes = scancodes.from_string("a\nb")
        self.assertEqual([(0x1e,), (0x30,)], codes)

    def test_wait(self):
        codes = scancodes.from_string("a<Wait>b")
        self.assertEqual([(0x1e,), ('wait',), (0x30,)], codes)
