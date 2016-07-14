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
