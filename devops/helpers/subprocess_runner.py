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

import fcntl
import os
import select
import subprocess
import threading
import time

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
        def poll_stream(src, verb_logger=None):
            dst = []
            try:
                for line in src:
                    dst.append(line)
                    if verb_logger is not None:
                        verb_logger(
                            line.decode('utf-8',
                                        errors='backslashreplace').rstrip()
                        )
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
                    result.stdout += poll_stream(
                        src=stdout,
                        verb_logger=logger.info if verbose else logger.debug)
                if stderr in rlist:
                    result.stderr += poll_stream(
                        src=stderr,
                        verb_logger=logger.error if verbose else logger.debug)

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
                time.sleep(0.1)
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
                        verb_logger=logger.info if verbose else logger.debug)
                    result.stderr += poll_stream(
                        src=proc.stderr,
                        verb_logger=logger.error if verbose else logger.debug)

                    stop.set()

        # 1 Command per run
        with cls.__lock:
            result = exec_result.ExecResult(cmd=command)
            stop_event = threading.Event()
            message = "\n".join(
                "\nExecuting command: {!r}".format(command.rstrip()).split(
                    "\\n"))

            if verbose:
                logger.info(message)
            else:
                logger.debug(message)
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

            wait_err_msg = ('Wait for {0!r} during {1}s: no return code!\n'
                            .format(command, timeout))
            output_brief_msg = ('\tSTDOUT:\n'
                                '{0}\n'
                                '\tSTDERR"\n'
                                '{1}'.format(result.stdout_brief,
                                             result.stderr_brief))
            logger.debug(wait_err_msg)
            raise error.TimeoutError(wait_err_msg + output_brief_msg)

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
        result = cls.__exec_command(command=command, timeout=timeout,
                                    verbose=verbose, **kwargs)
        message = (
            '\n{cmd!r} execution results: Exit code: {code!s}'.format(
                cmd=command,
                code=result.exit_code
            ))
        if verbose:
            logger.info(message)
        else:
            logger.debug(message)

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
                "expected {expected!s}\n".format(
                    append=error_info + '\n' if error_info else '',
                    cmd=command,
                    code=ret['exit_code'],
                    expected=expected
                ))
            logger.error(message)
            if raise_on_err:
                raise error.DevopsCalledProcessError(
                    command, ret['exit_code'],
                    expected=expected,
                    stdout=ret['stdout_brief'],
                    stderr=ret['stderr_brief'])
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
                "\texit code: {code!s}\n".format(
                    append=error_info + '\n' if error_info else '',
                    cmd=command,
                    code=ret['exit_code']
                ))
            logger.error(message)
            if raise_on_err:
                raise error.DevopsCalledProcessError(
                    command, ret['exit_code'],
                    stdout=ret['stdout_brief'],
                    stderr=ret['stderr_brief'])
        return ret
