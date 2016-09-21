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

import functools
import inspect
import threading
import time

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
