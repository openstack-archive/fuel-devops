#    Copyright 2013 - 2014 Mirantis, Inc.
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

from warnings import warn

import six


class DevopsError(Exception):
    """Base class for errors"""


class AuthenticationError(DevopsError):
    pass


class DevopsCalledProcessError(DevopsError):
    @staticmethod
    def _makestr(data):
        if isinstance(data, six.binary_type):
            return data.decode('utf-8', errors='backslashreplace')
        elif isinstance(data, six.text_type):
            return data
        else:
            return repr(data)

    def __init__(
            self, command, returncode, expected=0, stdout=None, stderr=None):
        self.returncode = returncode
        self.expected = expected
        self.cmd = command
        self.stdout = stdout
        self.stderr = stderr
        message = (
            "Command '{cmd}' returned exit code {code} while "
            "expected {expected}".format(
                cmd=self._makestr(self.cmd),
                code=self.returncode,
                expected=self.expected
            ))
        if self.stdout:
            message += "\n\tSTDOUT:\n{}".format(self._makestr(self.stdout))
        if self.stderr:
            message += "\n\tSTDERR:\n{}".format(self._makestr(self.stderr))
        super(DevopsCalledProcessError, self).__init__(message)

    @property
    def output(self):
        warn(
            'output is deprecated, please use stdout and stderr separately',
            DeprecationWarning)
        return self.stdout + self.stderr


class DevopsNotImplementedError(DevopsError, NotImplementedError):
    pass


class DevopsEnvironmentError(DevopsError, EnvironmentError):
    def __init__(self, command):
        self.cmd = command
        super(DevopsEnvironmentError, self).__init__(
            "Command '{!r}' is not found".format(self.cmd)
        )


class TimeoutError(DevopsError):
    pass
