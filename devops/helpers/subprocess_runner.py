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

from subprocess import PIPE
from subprocess import Popen
from threading import Event
from threading import RLock
from time import sleep

from six import with_metaclass

from devops.error import DevopsCalledProcessError
from devops.error import TimeoutError
from devops.helpers.decorators import threaded
from devops.helpers.exec_result import ExecResult
from devops.helpers.metaclasses import SingletonMeta
from devops import logger


class Subprocess(with_metaclass(SingletonMeta, object)):
    def __init__(self):
        self.__lock = RLock()
        self.__stop_read = Event()
        self.__stdout = []
        self.__stderr = []
        self.__return_code = None

    @property
    def lock(self):
        return self.__lock

    def __exec_command(self, command, cwd=None, env=None, timeout=None):
        @threaded(started=True)
        def poll_pipes(proc):
            while not self.__stop_read.isSet():
                sleep(0.1)

                self.__stdout += proc.stdout.readlines()
                self.__stderr += proc.stderr.readlines()

                proc.poll()

                if proc.returncode is not None:
                    self.__return_code = proc.returncode
                    self.__stdout += proc.stdout.readlines()
                    self.__stderr += proc.stderr.readlines()

                    self.__stop_read.set()

        # 1 Command per run
        with self.lock:
            process = Popen(
                args=[command],
                stdin=PIPE, stdout=PIPE, stderr=PIPE,
                shell=True, cwd=cwd, env=env,
                universal_newlines=False)

            # Poll output
            poll_pipes(process)
            # wait for process close
            self.__stop_read.wait(timeout)

            # Make result
            result = ExecResult(
                cmd=command,
                stdout=self.__stdout,
                stderr=self.__stderr,
            )

            # Clean-up
            self.__stdout = []
            self.__stderr = []
            self.__stop_read.clear()

            if self.__return_code is not None:
                result.exit_code = self.__return_code
                self.__return_code = None
                return result

            # Kill not ended process
            process.kill()

            status_tmpl = (
                'Wait for {0} during {1}s: no return code!\n'
                '\tSTDOUT:\n'
                '{2}\n'
                '\tSTDERR"\n'
                '{3}')
            logger.debug(
                status_tmpl.format(
                    command, timeout,
                    result.stdout,
                    result.stderr
                )
            )
            raise TimeoutError(
                status_tmpl.format(
                    command, timeout,
                    result.stdout_brief,
                    result.stderr_brief
                ))

    def execute(self, command, verbose=False, timeout=None):
        """Execute command and wait for return code

        :type command: str
        :type verbose: bool
        :type timeout: int
        :rtype: ExecResult
        :raises: TimeoutError
        """
        logger.debug("Executing command: '{}'".format(command.rstrip()))
        result = self.__exec_command(command=command, timeout=timeout)
        if verbose:
            logger.info(
                '{cmd} execution results:\n'
                'Exit code: {code}\n'
                'STDOUT:\n'
                '{stdout}\n'
                'STDERR:\n'
                '{stderr}'.format(
                    cmd=command,
                    code=result.exit_code,
                    stdout=result.stdout_str,
                    stderr=result.stderr_str
                ))
        else:
            logger.debug(
                '{cmd} execution results: Exit code: {code}'.format(
                    cmd=command,
                    code=result.exit_code
                )
            )

        return result

    def check_call(
            self,
            command, verbose=False, timeout=None,
            error_info=None,
            expected=None, raise_on_err=True):
        """Execute command and check for return code

        :type command: str
        :type verbose: bool
        :type timeout: int
        :type error_info: str
        :type expected: list
        :type raise_on_err: bool
        :rtype: ExecResult
        :raises: DevopsCalledProcessError
        """

        if expected is None:
            expected = [0]
        ret = self.execute(command, verbose, timeout)
        if ret['exit_code'] not in expected:
            message = (
                "{append}Command '{cmd}' returned exit code {code} while "
                "expected {expected}\n"
                "\tSTDOUT:\n"
                "{stdout}"
                "\n\tSTDERR:\n"
                "{stderr}".format(
                    append=error_info + '\n' if error_info else '',
                    cmd=command,
                    code=ret['exit_code'],
                    expected=expected,
                    stdout=ret['stdout_str'],
                    stderr=ret['stderr_str']
                ))
            logger.error(message)
            if raise_on_err:
                raise DevopsCalledProcessError(
                    command, ret['exit_code'],
                    expected=expected,
                    stdout=ret['stdout_str'],
                    stderr=ret['stderr_str'])
        return ret

    def check_stderr(
            self,
            command, verbose=False, timeout=None,
            error_info=None,
            raise_on_err=True):
        """Execute command expecting return code 0 and empty STDERR

        :type command: str
        :type verbose: bool
        :type timeout: int
        :type error_info: str
        :type raise_on_err: bool
        :rtype: ExecResult
        :raises: DevopsCalledProcessError
        """
        ret = self.check_call(
            command, verbose, timeout=timeout,
            error_info=error_info, raise_on_err=raise_on_err)
        if ret['stderr']:
            message = (
                "{append}Command '{cmd}' STDERR while not expected\n"
                "\texit code: {code}\n"
                "\tSTDOUT:\n"
                "{stdout}"
                "\n\tSTDERR:\n"
                "{stderr}".format(
                    append=error_info + '\n' if error_info else '',
                    cmd=command,
                    code=ret['exit_code'],
                    stdout=ret['stdout_str'],
                    stderr=ret['stderr_str']
                ))
            logger.error(message)
            if raise_on_err:
                raise DevopsCalledProcessError(command, ret['exit_code'],
                                               stdout=ret['stdout_str'],
                                               stderr=ret['stderr_str'])
        return ret
