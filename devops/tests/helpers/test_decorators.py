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

from devops.helpers import decorators
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


class TestProcLock(TestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        self.sleep_mock = self.patch(
            'time.sleep')

    def create_class_with_proc_lock(self, path, timeout):
        class MyClass(object):
            def __init__(self, method):
                self.m = method

            @decorators.proc_lock(path=path, timeout=timeout)
            def method(self):
                return self.m()

        return MyClass

    @mock.patch('fasteners.InterProcessLock.acquire')
    @mock.patch('fasteners.InterProcessLock.release')
    def test_default_no_proc_lock(self, release, acquire):
        method_mock = mock.Mock()

        # noinspection PyPep8Naming
        MyClass = self.create_class_with_proc_lock(None, 10)
        c = MyClass(method_mock)

        c.method()

        acquire.assert_not_called()
        method_mock.assert_called_once()
        release.assert_not_called()

    @mock.patch('fasteners.InterProcessLock.acquire')
    @mock.patch('fasteners.InterProcessLock.release')
    def test_passed_proc_lock(self, release, acquire):
        acquire.return_value = True
        method_mock = mock.Mock()

        # noinspection PyPep8Naming
        MyClass = self.create_class_with_proc_lock('/run/lock/devops_lock', 20)
        c = MyClass(method_mock)

        c.method()

        acquire.assert_called_once()
        method_mock.assert_called_once()
        release.assert_called_once()

    @mock.patch('fasteners.InterProcessLock.acquire')
    @mock.patch('fasteners.InterProcessLock.release')
    def test_acquire_timeout(self, release, acquire):
        acquire.return_value = False
        method_mock = mock.Mock()

        # noinspection PyPep8Naming
        MyClass = self.create_class_with_proc_lock('/run/lock/devops_lock', 30)
        c = MyClass(method_mock)

        with self.assertRaises(error.DevopsException):
            c.method()

        acquire.assert_called_once()
        method_mock.assert_not_called()
        release.assert_not_called()
