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

from __future__ import print_function
from __future__ import unicode_literals

import fcntl
import os
import select
import subprocess
import threading

import six

from devops import error
from devops.helpers import decorators
from devops.helpers import exec_result
from devops.helpers import metaclasses
from devops.helpers import proc_enums
from devops import logger


class Subprocess(six.with_metaclass(metaclasses.SingletonMeta, object)):
    __lock = threading.RLock()

    def __init__(self):
        """Subprocess helper with timeouts and lock-free FIFO

        For excluding race-conditions we allow to run 1 command simultaneously
        """
        pass

    @classmethod
    def __exec_command(cls, command, cwd=None, env=None, timeout=None,
                       verbose=False):
        """Command executor helper

        :type command: str
        :type cwd: str
        :type env: dict
        :type timeout: int
        :rtype: ExecResult
        """
        def poll_stream(src, verbose):
            dst = []
            try:
                for line in src:
                    dst.append(line)
                    if verbose:
                        print(
                            line.decode(
                                'utf-8',
                                errors='backslashreplace'),
                            end="")
            except IOError:
                pass
            return dst

        def poll_streams(result, stdout, stderr, verbose):
            rlist, _, _ = select.select(
                [stdout, stderr],
                [],
                [])
            if rlist:
                if stdout in rlist:
                    result.stdout += poll_stream(src=stdout, verbose=verbose)
                if stderr in rlist:
                    result.stderr += poll_stream(src=stderr, verbose=verbose)

        @decorators.threaded(started=True)
        def poll_pipes(proc, result, stop):
            """Polling task for FIFO buffers

            :type proc: subprocess.Popen
            :type result: ExecResult
            :type stop: threading.Event
            """
            # Get file descriptors for stdout and stderr streams
            fd_stdout = proc.stdout.fileno()
            fd_stderr = proc.stderr.fileno()
            # Get flags of stdout and stderr streams
            fl_stdout = fcntl.fcntl(fd_stdout, fcntl.F_GETFL)
            fl_stderr = fcntl.fcntl(fd_stderr, fcntl.F_GETFL)
            # Set nonblock mode for stdout and stderr streams
            fcntl.fcntl(fd_stdout, fcntl.F_SETFL, fl_stdout | os.O_NONBLOCK)
            fcntl.fcntl(fd_stderr, fcntl.F_SETFL, fl_stderr | os.O_NONBLOCK)

            while not stop.isSet():
                poll_streams(
                    result=result,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    verbose=verbose
                )

                proc.poll()

                if proc.returncode is not None:
                    result.exit_code = proc.returncode
                    result.stdout += poll_stream(
                        src=proc.stdout,
                        verbose=verbose)
                    result.stderr += poll_stream(
                        src=proc.stderr,
                        verbose=verbose)

                    stop.set()

        # 1 Command per run
        with cls.__lock:
            result = exec_result.ExecResult(cmd=command)
            stop_event = threading.Event()

            if verbose:
                print("\nExecuting command: {!r}".format(command.rstrip()))

            # Run
            process = subprocess.Popen(
                args=[command],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
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
                    "{!r} has been completed just after timeout: "
                    "please validate timeout.".format(command))

            status_tmpl = (
                'Wait for {0!r} during {1}s: no return code!\n'
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
            raise error.TimeoutError(
                status_tmpl.format(
                    command, timeout,
                    result.stdout_brief,
                    result.stderr_brief
                ))

    @classmethod
    def execute(cls, command, verbose=False, timeout=None, **kwargs):
        """Execute command and wait for return code

        Timeout limitation: read tick is 100 ms.

        :type command: str
        :type verbose: bool
        :type timeout: int
        :rtype: ExecResult
        :raises: TimeoutError
        """
        logger.debug("Executing command: {!r}".format(command.rstrip()))
        result = cls.__exec_command(command=command, timeout=timeout,
                                    verbose=verbose, **kwargs)
        if verbose:
            print(
                '\n{cmd!r} execution results: Exit code: {code!s}'.format(
                    cmd=command,
                    code=result.exit_code
                )
            )
            logger.debug(
                '{cmd!r} execution results:\n'
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
                '{cmd!r} execution results:\n'
                'Exit code: {code!s}\n'
                'BRIEF STDOUT:\n'
                '{stdout}\n'
                'BRIEF STDERR:\n'
                '{stderr}'.format(
                    cmd=command,
                    code=result.exit_code,
                    stdout=result.stdout_brief,
                    stderr=result.stderr_brief
                ))

        return result

    @classmethod
    def check_call(
            cls,
            command, verbose=False, timeout=None,
            error_info=None,
            expected=None, raise_on_err=True, **kwargs):
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
            expected = [proc_enums.ExitCodes.EX_OK]
        else:
            expected = [
                proc_enums.ExitCodes(code)
                if (
                    isinstance(code, int) and
                    code in proc_enums.ExitCodes.__members__.values())
                else code
                for code in expected
                ]
        ret = cls.execute(command, verbose, timeout, **kwargs)
        if ret['exit_code'] not in expected:
            message = (
                "{append}Command '{cmd!r}' returned exit code {code!s} while "
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
                raise error.DevopsCalledProcessError(
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
            raise_on_err=True, **kwargs):
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
            error_info=error_info, raise_on_err=raise_on_err, **kwargs)
        if ret['stderr']:
            message = (
                "{append}Command '{cmd!r}' STDERR while not expected\n"
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
                raise error.DevopsCalledProcessError(
                    command, ret['exit_code'],
                    stdout=ret['stdout_str'],
                    stderr=ret['stderr_str'])
        return ret
