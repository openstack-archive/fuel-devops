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

import logging
import threading
import unittest

import mock

from devops import error
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


@mock.patch('devops.helpers.decorators.logger', autospec=True)
class TestLogWrap(unittest.TestCase):
    def test_no_args(self, logger):
        @decorators.logwrap
        def func():
            return 'No args'

        result = func()
        self.assertEqual(result, 'No args')
        logger.assert_has_calls((
            mock.call.log(
                level=logging.DEBUG,
                msg="Calling: \n'func'()"
            ),
            mock.call.log(
                level=logging.DEBUG,
                msg="Done: 'func' with result:\n{}".format(
                    decorators.pretty_repr(result))
            ),
        ))

    def test_args_simple(self, logger):
        arg = 'test arg'

        @decorators.logwrap
        def func(tst):
            return tst

        result = func(arg)
        self.assertEqual(result, arg)
        logger.assert_has_calls((
            mock.call.log(
                level=logging.DEBUG,
                msg="Calling: \n'func'(\n    'tst'={},\n)".format(
                    decorators.pretty_repr(arg, indent=8, no_indent_start=True)
                )
            ),
            mock.call.log(
                level=logging.DEBUG,
                msg="Done: 'func' with result:\n{}".format(
                    decorators.pretty_repr(result))
            ),
        ))

    def test_args_defaults(self, logger):
        arg = 'test arg'

        @decorators.logwrap
        def func(tst=arg):
            return tst

        result = func()
        self.assertEqual(result, arg)
        logger.assert_has_calls((
            mock.call.log(
                level=logging.DEBUG,
                msg="Calling: \n'func'(\n    'tst'={},\n)".format(
                    decorators.pretty_repr(arg, indent=8,
                                           no_indent_start=True))
            ),
            mock.call.log(
                level=logging.DEBUG,
                msg="Done: 'func' with result:\n{}".format(
                    decorators.pretty_repr(result))
            ),
        ))

    def test_args_complex(self, logger):
        string = 'string'
        dictionary = {'key': 'dictionary'}

        @decorators.logwrap
        def func(param_string, param_dictionary):
            return param_string, param_dictionary

        result = func(string, dictionary)
        self.assertEqual(result, (string, dictionary))
        # raise ValueError(logger.mock_calls)
        logger.assert_has_calls((
            mock.call.log(
                level=logging.DEBUG,
                msg="Calling: \n'func'("
                    "\n    'param_string'={string},"
                    "\n    'param_dictionary'={dictionary},\n)".format(
                        string=decorators.pretty_repr(
                            string,
                            indent=8, no_indent_start=True),
                        dictionary=decorators.pretty_repr(
                            dictionary,
                            indent=8, no_indent_start=True)
                    )
            ),
            mock.call.log(
                level=logging.DEBUG,
                msg="Done: 'func' with result:\n{}".format(
                    decorators.pretty_repr(result))
            ),
        ))

    def test_args_kwargs(self, logger):
        targs = ['string1', 'string2']
        tkwargs = {'key': 'tkwargs'}

        @decorators.logwrap
        def func(*args, **kwargs):
            return tuple(args), kwargs

        result = func(*targs, **tkwargs)
        self.assertEqual(result, (tuple(targs), tkwargs))
        # raise ValueError(logger.mock_calls)
        logger.assert_has_calls((
            mock.call.log(
                level=logging.DEBUG,
                msg="Calling: \n'func'("
                    "\n    'args'={args},"
                    "\n    'kwargs'={kwargs},\n)".format(
                        args=decorators.pretty_repr(
                            tuple(targs),
                            indent=8, no_indent_start=True),
                        kwargs=decorators.pretty_repr(
                            tkwargs,
                            indent=8, no_indent_start=True)
                    )
            ),
            mock.call.log(
                level=logging.DEBUG,
                msg="Done: 'func' with result:\n{}".format(
                    decorators.pretty_repr(result))
            ),
        ))

    def test_negative(self, logger):
        @decorators.logwrap
        def func():
            raise ValueError('as expected')

        with self.assertRaises(ValueError):
            func()

        logger.assert_has_calls((
            mock.call.log(
                level=logging.DEBUG,
                msg="Calling: \n'func'()"
            ),
            mock.call.log(
                level=logging.ERROR,
                msg="Failed: \n'func'()",
                exc_info=True
            ),
        ))

    def test_negative_substitutions(self, logger):
        new_logger = mock.Mock(spec=logging.Logger, name='logger')
        log = mock.Mock(name='log')
        new_logger.attach_mock(log, 'log')

        @decorators.logwrap(
            log=new_logger,
            log_level=logging.INFO,
            exc_level=logging.WARNING
        )
        def func():
            raise ValueError('as expected')

        with self.assertRaises(ValueError):
            func()

        self.assertEqual(len(logger.mock_calls), 0)
        log.assert_has_calls((
            mock.call(
                level=logging.INFO,
                msg="Calling: \n'func'()"
            ),
            mock.call(
                level=logging.WARNING,
                msg="Failed: \n'func'()",
                exc_info=True
            ),
        ))
