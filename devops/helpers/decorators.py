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

from functools import wraps
from threading import Thread

import fasteners

from devops import error
from devops import logger
from devops import settings


def threaded(name=None, started=False, daemon=False):
    """Make function or method threaded with passing arguments

    If decorator added not as function, name is generated from function name.

    :type name: str
    :type started: bool
    :type daemon: bool
    """

    def real_decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            """Thread generator for function

            :rtype: Thread
            """
            if name is None:
                func_name = 'Threaded {}'.format(func.__name__)
            else:
                func_name = name
            thread = Thread(
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


def proc_lock(path=settings.DEVOPS_LOCK_FILE, timeout=300):
    """Process lock based on fcntl.lockf

    Avoid race condition between different processes which
    use fuel-devops at the same time during the resources
    creation/modification/erase.

    :param path: str, path to the lock file
    :param timeout: int, timeout in second for waiting the lock file
    """
    def real_decorator(func):
        @wraps(func)
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
                    raise error.DevopsError(
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
