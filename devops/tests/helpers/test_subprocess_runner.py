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
from unittest import TestCase

from mock import call
from mock import Mock
from mock import patch

from devops.error import DevopsCalledProcessError
from devops.helpers.exec_result import ExecResult
from devops.helpers.subprocess_runner import Subprocess

command = 'ls ~ '


# TODO(AStepanov): Cover negative scenarios (timeout)


@patch('devops.helpers.subprocess_runner.logger', autospec=True)
@patch(
    'devops.helpers.subprocess_runner.Popen', autospec=True,
    name='subprocess.Popen')
class TestSubprocessRunner(TestCase):
    @staticmethod
    def prepare_close(popen, stderr_val=None, ec=0):
        stdout_lines = [b' \n', b'2\n', b'3\n', b' \n']
        stderr_lines = (
            [b' \n', b'0\n', b'1\n', b' \n'] if stderr_val is None else []
        )
        stderr_readlines = Mock(
            side_effect=[
                stderr_lines,
                [],
                [],
            ]
        )
        stdout_readlines = Mock(
            side_effect=[
                stdout_lines,
                [],
                [],
            ]
        )

        stdout = Mock()
        stderr = Mock()

        stdout.attach_mock(stdout_readlines, 'readlines')
        stderr.attach_mock(stderr_readlines, 'readlines')

        popen_obj = Mock()
        popen_obj.attach_mock(stdout, 'stdout')
        popen_obj.attach_mock(stderr, 'stderr')
        popen_obj.configure_mock(returncode=ec)

        popen.return_value = popen_obj

        exp_result = ExecResult(
            cmd=command,
            stderr=stderr_lines,
            stdout=stdout_lines,
            exit_code=ec
            )

        return popen_obj, exp_result

    def test_call(self, popen, logger):
        popen_obj, exp_result = self.prepare_close(popen)

        runner = Subprocess()

        result = runner.execute(command)
        self.assertEqual(
            result, exp_result

        )
        popen.assert_has_calls((
            call(args=[command], cwd=None, env=None, shell=True, stderr=PIPE,
                 stdin=PIPE, stdout=PIPE, universal_newlines=False),
        ))
        logger.assert_has_calls((
            call.debug("Executing command: '{}'".format(command.rstrip())),
            call.debug(
                '{cmd} execution results: Exit code: {code}'.format(
                    cmd=command,
                    code=result.exit_code
                )),
        ))
        popen_obj.assert_has_calls((
            call.stdout.readlines(),
            call.stderr.readlines(),
            call.poll(),
            call.stdout.readlines(),
            call.stderr.readlines()
        ))

    def test_call_verbose(self, popen, logger):
        _, _ = self.prepare_close(popen)

        runner = Subprocess()

        result = runner.execute(command, verbose=True)

        logger.assert_has_calls((
            call.debug("Executing command: '{}'".format(command.rstrip())),
            call.info(
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
                )),
        ))

    @patch('devops.helpers.subprocess_runner.Subprocess.execute')
    def test_check_call(self, execute, popen, logger):
        exit_code = 0
        return_value = {
            'stderr_str': '0\n1',
            'stdout_str': '2\n3',
            'exit_code': exit_code,
            'stderr': [b' \n', b'0\n', b'1\n', b' \n'],
            'stdout': [b' \n', b'2\n', b'3\n', b' \n']}
        execute.return_value = return_value

        verbose = False

        runner = Subprocess()

        # noinspection PyTypeChecker
        result = runner.check_call(
            command=command, verbose=verbose, timeout=None)
        execute.assert_called_once_with(command, verbose, None)
        self.assertEqual(result, return_value)

        exit_code = 1
        return_value['exit_code'] = exit_code
        execute.reset_mock()
        execute.return_value = return_value
        with self.assertRaises(DevopsCalledProcessError):
            # noinspection PyTypeChecker
            runner.check_call(command=command, verbose=verbose, timeout=None)
        execute.assert_called_once_with(command, verbose, None)

    @patch('devops.helpers.subprocess_runner.Subprocess.check_call')
    def test_check_stderr(self, check_call, popen, logger):
        return_value = {
            'stderr_str': '',
            'stdout_str': '2\n3',
            'exit_code': 0,
            'stderr': [],
            'stdout': [b' \n', b'2\n', b'3\n', b' \n']}
        check_call.return_value = return_value

        verbose = False
        raise_on_err = True

        runner = Subprocess()

        # noinspection PyTypeChecker
        result = runner.check_stderr(
            command=command, verbose=verbose, timeout=None,
            raise_on_err=raise_on_err)
        check_call.assert_called_once_with(
            command, verbose, timeout=None,
            error_info=None, raise_on_err=raise_on_err)
        self.assertEqual(result, return_value)

        return_value['stderr_str'] = '0\n1'
        return_value['stderr'] = [b' \n', b'0\n', b'1\n', b' \n']

        check_call.reset_mock()
        check_call.return_value = return_value
        with self.assertRaises(DevopsCalledProcessError):
            # noinspection PyTypeChecker
            runner.check_stderr(
                command=command, verbose=verbose, timeout=None,
                raise_on_err=raise_on_err)
        check_call.assert_called_once_with(
            command, verbose, timeout=None,
            error_info=None, raise_on_err=raise_on_err)
