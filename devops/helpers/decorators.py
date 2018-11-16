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
import logging
import time
import warnings

import fasteners
import logwrap as ext_logwrap
import threaded as ext_threaded

from devops import error
from devops import logger
from devops import settings


def threaded(name=None, started=False, daemon=False):
    warnings.warn(
        'helpers.decorators.threaded is deprecated'
        ' in favor of external threaded',
        DeprecationWarning
    )
    return ext_threaded.threaded(name=name, started=started, daemon=daemon)


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


def pretty_repr(src, indent=0, no_indent_start=False, max_indent=20):
    warnings.warn(
        'helpers.decorators.pretty_repr is deprecated'
        ' in favor of external logwrap',
        DeprecationWarning
    )
    return ext_logwrap.pretty_repr(
        src=src,
        indent=indent,
        no_indent_start=no_indent_start,
        max_indent=max_indent
    )


def logwrap(log=logger, log_level=logging.DEBUG, exc_level=logging.ERROR):
    warnings.warn(
        'helpers.decorators.logwrap is deprecated'
        ' in favor of external logwrap',
        DeprecationWarning
    )
    return ext_logwrap.logwrap(
        func=log if callable(log) else None,
        log=log if isinstance(log, logging.Logger) else logger,
        log_level=log_level,
        exc_level=exc_level
    )


def proc_lock(path=settings.DEVOPS_LOCK_FILE, timeout=300):
    """Process lock based on fcntl.lockf

    Avoid race condition between different processes which
    use fuel-devops at the same time during the resources
    creation/modification/erase.

    :param path: str, path to the lock file
    :param timeout: int, timeout in second for waiting the lock file
    """
    def real_decorator(func):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            acquired = False
            if path is not None:
                logger.debug('Acquiring lock file {0} for {1}'
                             .format(path, func.__name__))
                lock = fasteners.InterProcessLock(path)
                acquired = lock.acquire(blocking=True,
                                        delay=5, timeout=timeout)
                logger.debug('Acquired the lock file {0} for {1}'
                             .format(path, func.__name__))
                if not acquired:
                    raise error.DevopsException(
                        'Failed to aquire lock file in {0} sec'
                        .format(timeout))
            try:
                result = func(*args, **kwargs)
            finally:
                if acquired:
                    logger.debug('Releasing the lock file {0} for {1}'
                                 .format(path, func.__name__))
                    lock.release()
            return result
        return wrapped
    return real_decorator
