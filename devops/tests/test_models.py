#    Copyright 2013 - 2014 Mirantis, Inc.
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

import random
from django.utils import unittest
import threading
from devops.manager import Manager
from devops.models import double_tuple


class MyThread(threading.Thread):
    def run(self):
        Manager().network_create(str(random.randint(1, 5000)))


class TestModels(unittest.TestCase):
    def test_django_choices(self):
        self.assertEquals((('a', 'a'), ('b', 'b')), double_tuple('a', 'b'))
