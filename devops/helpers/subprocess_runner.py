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
from devops.helpers.proc_enums import ExitCodes
from devops import logger


class Subprocess(with_metaclass(SingletonMeta, object)):
    __lock = RLock()

    def __init__(self):
        """Subprocess helper with timeouts and lock-free FIFO

        For excluding race-conditions we allow to run 1 command simultaneously
        """
        pass

    @classmethod
    def __exec_command(cls, command, cwd=None, env=None, timeout=None):
        """Command executor helper

        :type command: str
        :type cwd: str
        :type env: dict
        :type timeout: int
        :rtype: ExecResult
        """

        @threaded(started=True)
        def poll_pipes(proc, result, stop):
            """Polling task for FIFO buffers

            :type proc: Popen
            :type result: ExecResult
            :type stop: Event
            """
            while not stop.isSet():
                sleep(0.1)

                result.stdout += proc.stdout.readlines()
                result.stderr += proc.stderr.readlines()

                proc.poll()

                if proc.returncode is not None:
                    result.exit_code = proc.returncode
                    result.stdout += proc.stdout.readlines()
                    result.stderr += proc.stderr.readlines()

                    stop.set()

        # 1 Command per run
        with cls.__lock:
            result = ExecResult(cmd=command)
            stop_event = Event()

            # Run
            process = Popen(
                args=[command],
                stdin=PIPE, stdout=PIPE, stderr=PIPE,
                shell=True, cwd=cwd, env=env,
                universal_newlines=False)

            # Poll output
            poll_pipes(process, result, stop_event)
            # wait for process close
            stop_event.wait(timeout)

            # Process closed?
            if stop_event.isSet():
                stop_event.clear()
                return result

            # Kill not ended process and wait for close
            try:
                process.kill()  # kill -9
                stop_event.wait(5)

            except OSError:
                # Nothing to kill
                logger.warning(
                    "{} has been completed just after timeout: "
                    "please validate timeout.".format(command))

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

    @classmethod
    def execute(cls, command, verbose=False, timeout=None):
        """Execute command and wait for return code

        Timeout limitation: read tick is 100 ms.

        :type command: str
        :type verbose: bool
        :type timeout: int
        :rtype: ExecResult
        :raises: TimeoutError
        """
        logger.debug("Executing command: '{}'".format(command.rstrip()))
        result = cls.__exec_command(command=command, timeout=timeout)
        if verbose:
            logger.info(
                '{cmd} execution results:\n'
                'Exit code: {code!s}\n'
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

    @classmethod
    def check_call(
            cls,
            command, verbose=False, timeout=None,
            error_info=None,
            expected=None, raise_on_err=True):
        """Execute command and check for return code

        Timeout limitation: read tick is 100 ms.

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
            expected = [ExitCodes.EX_OK]
        else:
            expected = [
                ExitCodes(code)
                if (
                    isinstance(code, int) and
                    code in ExitCodes.__members__.values())
                else code
                for code in expected
                ]
        ret = cls.execute(command, verbose, timeout)
        if ret['exit_code'] not in expected:
            message = (
                "{append}Command '{cmd}' returned exit code {code!s} while "
                "expected {expected!s}\n"
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

    @classmethod
    def check_stderr(
            cls,
            command, verbose=False, timeout=None,
            error_info=None,
            raise_on_err=True):
        """Execute command expecting return code 0 and empty STDERR

        Timeout limitation: read tick is 100 ms.

        :type command: str
        :type verbose: bool
        :type timeout: int
        :type error_info: str
        :type raise_on_err: bool
        :rtype: ExecResult
        :raises: DevopsCalledProcessError
        """
        ret = cls.check_call(
            command, verbose, timeout=timeout,
            error_info=error_info, raise_on_err=raise_on_err)
        if ret['stderr']:
            message = (
                "{append}Command '{cmd}' STDERR while not expected\n"
                "\texit code: {code!s}\n"
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
