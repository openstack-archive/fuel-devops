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

import collections
import functools
import inspect
import logging
import sys
import threading
import time

import six

from devops import error
from devops import logger


def threaded(name=None, started=False, daemon=False):
    """Make function or method threaded with passing arguments

    If decorator added not as function, name is generated from function name.

    :type name: str
    :type started: bool
    :type daemon: bool
    """

    def real_decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """Thread generator for function

            :rtype: Thread
            """
            if name is None:
                func_name = 'Threaded {}'.format(func.__name__)
            else:
                func_name = name
            thread = threading.Thread(
                target=func,
                name=func_name,
                args=args,
                kwargs=kwargs)
            if daemon:
                thread.daemon = True
            if started:
                thread.start()
            return thread
        return wrapper

    if name is not None and callable(name):
        func, name = name, None
        return real_decorator(func)

    return real_decorator


def retry(exception, count=10, delay=1):
    """Retry decorator

    Retries to run decorated method with the same parameters in case of
    thrown :exception:

    :type exception: class
    :param exception: exception class
    :type count: int
    :param count: retry count
    :type delay: int
    :param delay: delay between retries in seconds
    :rtype: function
    """
    def decorator(func):
        if inspect.ismethod(func):
            full_name = '{}:{}.{}'.format(
                inspect.getmodule(func.im_class).__name__,
                func.im_class.__name__,
                func.__name__)
        elif inspect.isfunction(func):
            full_name = '{}.{}'.format(
                inspect.getmodule(func).__name__,
                func.__name__)
        else:
            raise error.DevopsException(
                'Wrong func parameter type {!r}'.format(func))

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            i = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exception as e:
                    i += 1
                    if i >= count:
                        raise

                    logger.debug(
                        'Exception {!r} while running {!r}. '
                        'Waiting {} seconds.'.format(e, func.__name__, delay),
                        exc_info=True)  # logs traceback
                    time.sleep(delay)

                    arg_str = ', '.join((
                        ', '.join(map(repr, args)),
                        ', '.join('{}={!r}'.format(k, v) for k, v in kwargs),
                    ))
                    logger.debug('Retrying {}({})'.format(full_name, arg_str))

        return wrapper

    return decorator


# pylint: disable=no-member
def _get_arg_names(func):
    """get argument names for function

    :param func: func
    :return: list of function argnames
    :rtype: list

    >>> def tst_1():
    ...     pass

    >>> _get_arg_names(tst_1)
    []

    >>> def tst_2(arg):
    ...     pass

    >>> _get_arg_names(tst_2)
    ['arg']
    """
    # noinspection PyUnresolvedReferences
    return (
        [arg for arg in inspect.getargspec(func=func).args] if six.PY2 else
        list(inspect.signature(obj=func).parameters.keys())
    )


def _getcallargs(func, *positional, **named):
    """get real function call arguments without calling function

    :rtype: dict
    """
    # noinspection PyUnresolvedReferences
    if sys.version_info[0:2] < (3, 5):  # apply_defaults is py35 feature
        orig_args = inspect.getcallargs(func, *positional, **named)
        # Construct OrderedDict as Py3
        arguments = collections.OrderedDict(
            [(key, orig_args[key]) for key in _get_arg_names(func)]
        )
        if six.PY2:
            # args and kwargs is not bound in py27
            # Note: py27 inspect is not unicode
            if 'args' in orig_args:
                arguments[b'args'] = orig_args['args']
            if 'kwargs' in orig_args:
                arguments[b'kwargs'] = orig_args['kwargs']
        return arguments
    sig = inspect.signature(func).bind(*positional, **named)
    sig.apply_defaults()  # after bind we doesn't have defaults
    return sig.arguments
# pylint:enable=no-member


def _simple(item):
    """Check for nested iterations: True, if not"""
    return not isinstance(item, (list, set, tuple, dict))


_formatters = {
    'simple': "{spc:<{indent}}{val!r}".format,
    'text': "{spc:<{indent}}{prefix}'''{string}'''".format,
    'dict': "\n{spc:<{indent}}{key!r:{size}}: {val},".format,
    }


def pretty_repr(src, indent=0, no_indent_start=False, max_indent=20):
    """Make human readable repr of object

    :param src: object to process
    :type src: object
    :param indent: start indentation, all next levels is +4
    :type indent: int
    :param no_indent_start: do not indent open bracket and simple parameters
    :type no_indent_start: bool
    :param max_indent: maximal indent before classic repr() call
    :type max_indent: int
    :return: formatted string
    """
    if _simple(src) or indent >= max_indent:
        indent = 0 if no_indent_start else indent
        if isinstance(src, (six.binary_type, six.text_type)):
            if isinstance(src, six.binary_type):
                string = src.decode(
                    encoding='utf-8',
                    errors='backslashreplace'
                )
                prefix = 'b'
            else:
                string = src
                prefix = ''
            return _formatters['text'](
                spc='',
                indent=indent,
                prefix=prefix,
                string=string
            )
        return _formatters['simple'](
            spc='',
            indent=indent,
            val=src
        )
    if isinstance(src, dict):
        prefix, suffix = '{', '}'
        result = ''
        max_len = len(max([repr(key) for key in src])) if src else 0
        for key, val in src.items():
            result += _formatters['dict'](
                spc='',
                indent=indent + 4,
                size=max_len,
                key=key,
                val=pretty_repr(val, indent + 8, no_indent_start=True)
            )
        return (
            '\n{start:>{indent}}'.format(
                start=prefix,
                indent=indent + 1
            ) +
            result +
            '\n{end:>{indent}}'.format(end=suffix, indent=indent + 1)
        )
    if isinstance(src, list):
        prefix, suffix = '[', ']'
    elif isinstance(src, tuple):
        prefix, suffix = '(', ')'
    else:
        prefix, suffix = '{', '}'
    result = ''
    for elem in src:
        if _simple(elem):
            result += '\n'
        result += pretty_repr(elem, indent + 4) + ','
    return (
        '\n{start:>{indent}}'.format(
            start=prefix,
            indent=indent + 1) +
        result +
        '\n{end:>{indent}}'.format(end=suffix, indent=indent + 1)
    )


def logwrap(log=logger, log_level=logging.DEBUG, exc_level=logging.ERROR):
    """Log function calls

    :type log: logging.Logger
    :type log_level: int
    :type exc_level: int
    :rtype: callable
    """
    def real_decorator(func):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            call_args = _getcallargs(func, *args, **kwargs)
            args_repr = ""
            if len(call_args) > 0:
                args_repr = "\n    " + "\n    ".join((
                    "{key!r}={val},".format(
                        key=key,
                        val=pretty_repr(val, indent=8, no_indent_start=True)
                    )
                    for key, val in call_args.items())
                ) + '\n'
            log.log(
                level=log_level,
                msg="Calling: \n{name!r}({arguments})".format(
                    name=func.__name__,
                    arguments=args_repr
                )
            )
            try:
                result = func(*args, **kwargs)
                log.log(
                    level=log_level,
                    msg="Done: {name!r} with result:\n{result}".format(
                        name=func.__name__,
                        result=pretty_repr(result))
                )
            except BaseException:
                log.log(
                    level=exc_level,
                    msg="Failed: \n{name!r}({arguments})".format(
                        name=func.__name__,
                        arguments=args_repr,
                    ),
                    exc_info=True
                )
                raise
            return result
        return wrapped

    if not isinstance(log, logging.Logger):
        func, log = log, logger
        return real_decorator(func)

    return real_decorator
