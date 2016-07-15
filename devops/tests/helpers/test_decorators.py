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

from threading import RLock
from unittest import TestCase

import mock

from devops.helpers.decorators import threaded


class ThreadedTest(TestCase):
    def test_add_basic(self):
        @threaded
        def func_test():
            pass
        test_thread = func_test()
        self.assertEqual(test_thread.name, 'Threaded func_test')
        self.assertFalse(test_thread.daemon)
        self.assertFalse(test_thread.isAlive())

    def test_add_func(self):
        @threaded()
        def func_test():
            pass

        test_thread = func_test()
        self.assertEqual(test_thread.name, 'Threaded func_test')
        self.assertFalse(test_thread.daemon)
        self.assertFalse(test_thread.isAlive())

    def test_name(self):
        @threaded(name='test name')
        def func_test():
            pass

        test_thread = func_test()
        self.assertEqual(test_thread.name, 'test name')
        self.assertFalse(test_thread.daemon)
        self.assertFalse(test_thread.isAlive())

    def test_daemon(self):
        @threaded(daemon=True)
        def func_test():
            pass

        test_thread = func_test()
        self.assertEqual(test_thread.name, 'Threaded func_test')
        self.assertTrue(test_thread.daemon)
        self.assertFalse(test_thread.isAlive())

    @mock.patch('devops.helpers.decorators.Thread', autospec=True)
    def test_started(self, thread):
        @threaded(started=True)
        def func_test():
            pass

        func_test()

        self.assertIn(mock.call().start(), thread.mock_calls)

    def test_args(self):
        lock = RLock()
        data = []
        global data

        @threaded(started=True)
        def func_test(add, rlock):
            with rlock:
                data.append(add)

        func_test(1, lock)
        with lock:
            self.assertEqual(data, [1])

    def test_kwargs(self):
        lock = RLock()
        data = []
        global data

        @threaded(started=True)
        def func_test(add, rlock):
            with rlock:
                data.append(add)

        func_test(add=2, rlock=lock)
        with lock:
            self.assertEqual(data, [2])
