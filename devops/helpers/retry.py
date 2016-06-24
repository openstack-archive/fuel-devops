#    Copyright 2013 - 2016 Mirantis, Inc.
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

import functools
import inspect
from time import sleep

from devops.error import DevopsException
from devops import logger


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
            raise DevopsException(
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
                    sleep(delay)

                    arg_str = ', '.join((
                        ', '.join(map(repr, args)),
                        ', '.join('{}={!r}'.format(k, v) for k, v in kwargs),
                    ))
                    logger.debug('Retrying {}({})'.format(full_name, arg_str))

        return wrapper

    return decorator
