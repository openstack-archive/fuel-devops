#    Copyright 2013 - 2015 Mirantis, Inc.
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


def lazy(fn):
    """Lazy decorator.

    Decorates a method which will be evalueted only one time. After that next
    calls return the same value stored in "_lazy_{method_name}" without
    calling the method.
    """

    # create lazy attr name "_lazy_{method_name}"
    attr_name = '_lazy_' + fn.__name__

    @functools.wraps(fn)
    def _lazy(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)

    return _lazy


def lazy_property(fn):
    return property(lazy(fn))
