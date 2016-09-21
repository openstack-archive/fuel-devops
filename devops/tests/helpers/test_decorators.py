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

import threading
import unittest

import mock

from devops.helpers import decorators


class ThreadedTest(unittest.TestCase):
    def test_add_basic(self):
        @decorators.threaded
        def func_test():
            pass
        # pylint: disable=assignment-from-no-return
        test_thread = func_test()
        # pylint: enable=assignment-from-no-return
        self.assertEqual(test_thread.name, 'Threaded func_test')
        self.assertFalse(test_thread.daemon)
        self.assertFalse(test_thread.isAlive())

    def test_add_func(self):
        @decorators.threaded()
        def func_test():
            pass

        # pylint: disable=assignment-from-no-return
        test_thread = func_test()
        # pylint: enable=assignment-from-no-return
        self.assertEqual(test_thread.name, 'Threaded func_test')
        self.assertFalse(test_thread.daemon)
        self.assertFalse(test_thread.isAlive())

    def test_name(self):
        @decorators.threaded(name='test name')
        def func_test():
            pass

        # pylint: disable=assignment-from-no-return
        test_thread = func_test()
        # pylint: enable=assignment-from-no-return
        self.assertEqual(test_thread.name, 'test name')
        self.assertFalse(test_thread.daemon)
        self.assertFalse(test_thread.isAlive())

    def test_daemon(self):
        @decorators.threaded(daemon=True)
        def func_test():
            pass

        # pylint: disable=assignment-from-no-return
        test_thread = func_test()
        # pylint: enable=assignment-from-no-return
        self.assertEqual(test_thread.name, 'Threaded func_test')
        self.assertTrue(test_thread.daemon)
        self.assertFalse(test_thread.isAlive())

    @mock.patch('threading.Thread', autospec=True)
    def test_started(self, thread):
        @decorators.threaded(started=True)
        def func_test():
            pass

        func_test()

        self.assertIn(mock.call().start(), thread.mock_calls)

    def test_args(self):
        event = threading.Event()
        data = []
        # pylint: disable=global-variable-not-assigned
        global data
        # pylint: enable=global-variable-not-assigned

        @decorators.threaded(started=True)
        def func_test(add, evnt):
            data.append(add)
            evnt.set()

        func_test(1, event)
        event.wait(3)
        self.assertEqual(data, [1])

    def test_kwargs(self):
        event = threading.Event()
        data = []
        # pylint: disable=global-variable-not-assigned
        global data
        # pylint: enable=global-variable-not-assigned

        @decorators.threaded(started=True)
        def func_test(add, evnt):
            data.append(add)
            evnt.set()

        func_test(add=2, evnt=event)
        event.wait(3)
        self.assertEqual(data, [2])
