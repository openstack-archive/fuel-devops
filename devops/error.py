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

import inspect
from warnings import warn


class DevopsException(Exception):
    """Base class for exceptions"""


class DevopsError(DevopsException):
    """Base class for errors"""


class AuthenticationError(DevopsError):
    pass


class DevopsCalledProcessError(DevopsError):
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
                cmd=self.cmd,
                code=self.returncode,
                expected=self.expected
            ))
        if self.stdout:
            message += "\n\tSTDOUT:\n{}".format(self.stdout)
        if self.stderr:
            message += "\n\tSTDERR:\n{}".format(self.stderr)
        super(DevopsCalledProcessError, self).__init__(message)

    @property
    def output(self):
        warn(
            'output is deprecated, please use stdout and stderr separately',
            DeprecationWarning)
        return self.stdout + self.stderr


class DevopsNotImplementedError(DevopsError):
    pass


class DevopsEnvironmentError(DevopsError):
    def __init__(self, command):
        self.cmd = command
        super(DevopsEnvironmentError, self).__init__(
            "Command '{0}' is not found".format(self.cmd)
        )


class TimeoutError(DevopsError):
    pass


class DevopsObjNotFound(DevopsError):
    """Object not found in Devops database"""

    def __init__(self, cls, *args, **kwargs):
        cls_name = '{}.{}'.format(inspect.getmodule(cls).__name__,
                                  cls.__name__)
        items = [repr(a) for a in args]
        items += ['{}={!r}'.format(k, v) for k, v in kwargs.items()]
        content = ', '.join(items)
        msg = '{cls_name}({content}) does not exist in database.'.format(
            cls_name=cls_name, content=content)
        super(DevopsObjNotFound, self).__init__(msg)
