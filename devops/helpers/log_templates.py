# coding=utf-8

#    Copyright 2017 Mirantis, Inc.
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

CMD_EXEC = u"\nExecuting command: '{cmd!s}'"
CMD_RESULT = (u"\nCommand '{cmd!s}'\nexecution results: "
              u"Exit code: '{code!s}'")
CMD_UNEXPECTED_EXIT_CODE = (u"{append}Command '{cmd!s}' returned "
                            u"exit code '{code!s}' while "
                            u"expected '{expected!s}'\n")
CMD_UNEXPECTED_STDERR = (u"{append}Command '{cmd!s}' STDERR while "
                         u"not expected\n"
                         u"\texit code: '{code!s}'")
CMD_WAIT_ERROR = (u"Wait for '{cmd!s}' during {timeout!s}s: "
                  u"no return code!")
