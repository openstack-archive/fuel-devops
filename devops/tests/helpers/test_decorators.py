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

import unittest

import mock

from devops import error
from devops.helpers import decorators


class TestRetry(unittest.TestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        self.sleep_mock = self.patch(
            'time.sleep')

    def create_class_with_retry(self, count, delay):
        class MyClass(object):
            def __init__(self, method):
                self.m = method

            @decorators.retry(TypeError, count=count, delay=delay)
            def method(self):
                return self.m()

        return MyClass

    def test_no_retry(self):
        method_mock = mock.Mock()

        # noinspection PyPep8Naming
        MyClass = self.create_class_with_retry(3, 5)
        c = MyClass(method_mock)

        c.method()

        method_mock.assert_called_once_with()

    def test_retry_3(self):
        method_mock = mock.Mock()
        method_mock.side_effect = (TypeError, TypeError, 3)

        # noinspection PyPep8Naming
        MyClass = self.create_class_with_retry(3, 5)
        c = MyClass(method_mock)

        assert c.method() == 3

        method_mock.assert_has_calls((
            mock.call(),
            mock.call(),
            mock.call(),
        ))
        self.sleep_mock.assert_has_calls((
            mock.call(5),
            mock.call(5),
        ))

    def test_retry_exception(self):
        method_mock = mock.Mock()
        method_mock.side_effect = (TypeError, TypeError, AttributeError)

        # noinspection PyPep8Naming
        MyClass = self.create_class_with_retry(3, 5)
        c = MyClass(method_mock)

        with self.assertRaises(AttributeError):
            c.method()

        method_mock.assert_has_calls((
            mock.call(),
            mock.call(),
            mock.call(),
        ))
        self.sleep_mock.assert_has_calls((
            mock.call(5),
            mock.call(5),
        ))

    def test_wrong_arg(self):
        retry_dec = decorators.retry(AttributeError)
        with self.assertRaises(error.DevopsException):
            retry_dec('wrong')


class TestPrettyRepr(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(
            decorators.pretty_repr(True), repr(True)
        )

    def test_text(self):
        self.assertEqual(
            decorators.pretty_repr('Unicode text'), "u'''Unicode text'''"
        )
        self.assertEqual(
            decorators.pretty_repr(b'bytes text\x01'), "b'''bytes text\x01'''"
        )

    def test_iterable(self):
        self.assertEqual(
            decorators.pretty_repr([1, 2, 3]),
            '\n[{nl:<5}1,{nl:<5}2,{nl:<5}3,\n]'.format(nl='\n')
        )
        self.assertEqual(
            decorators.pretty_repr((1, 2, 3)),
            '\n({nl:<5}1,{nl:<5}2,{nl:<5}3,\n)'.format(nl='\n')
        )
        res = decorators.pretty_repr({1, 2, 3})
        self.assertTrue(
            res.startswith('\n{') and res.endswith('\n}')
        )

    def test_dict(self):
        self.assertEqual(
            decorators.pretty_repr({1: 1, 2: 2, 33: 33}),
            '\n{\n    1 : 1,\n    2 : 2,\n    33: 33,\n}'
        )

    def test_nested_dict(self):
        test_obj = [
            {
                1:
                    {
                        2: 3
                    },
                4:
                    {
                        5: 6
                    },
            },
            {
                7: 8,
                9: (10, 11)
            },
            (
                12,
                13,
            ),
            {14: {15: {16: {17: {18: {19: [20]}}}}}}
        ]
        exp_repr = (
            '\n['
            '\n    {'
            '\n        1: '
            '\n            {'
            '\n                2: 3,'
            '\n            },'
            '\n        4: '
            '\n            {'
            '\n                5: 6,'
            '\n            },'
            '\n    },'
            '\n    {'
            '\n        9: '
            '\n            ('
            '\n                10,'
            '\n                11,'
            '\n            ),'
            '\n        7: 8,'
            '\n    },'
            '\n    ('
            '\n        12,'
            '\n        13,'
            '\n    ),'
            '\n    {'
            '\n        14: '
            '\n            {'
            '\n                15: {16: {17: {18: {19: [20]}}}},'
            '\n            },'
            '\n    },'
            '\n]'
        )
        self.assertEqual(decorators.pretty_repr(test_obj), exp_repr)


class TestProcLock(unittest.TestCase):

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
