#    Copyright 2013 Mirantis, Inc.
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

class DevopsError(Exception):
    message = "Devops Error"


class AuthenticationError(DevopsError):
    pass


class DevopsCalledProcessError(DevopsError):
    def __init__(self, command, returncode, output=None):
        self.returncode = returncode
        self.cmd = command
        self.output = output

    def __str__(self):
        message = "Command '%s' returned non-zero exit status %s" % (
            self.cmd, self.returncode)
        if self.output:
            message += "\n%s" % '\n'.join(self.output)
        return message


class DevopsNotImplementedError(DevopsError):
    pass


class TimeoutError(DevopsError):
    pass
