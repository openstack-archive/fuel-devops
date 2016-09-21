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

        MyClass = self.create_class_with_retry(3, 5)
        c = MyClass(method_mock)

        c.method()

        method_mock.assert_called_once_with()

    def test_retry_3(self):
        method_mock = mock.Mock()
        method_mock.side_effect = (TypeError, TypeError, 3)

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
