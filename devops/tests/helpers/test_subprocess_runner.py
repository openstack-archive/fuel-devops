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

import subprocess
import unittest

import mock

from devops import error
from devops.helpers import exec_result
from devops.helpers import subprocess_runner

command = 'ls ~ '


# TODO(AStepanov): Cover negative scenarios (timeout)


@mock.patch('devops.helpers.subprocess_runner.logger', autospec=True)
@mock.patch('fcntl.fcntl', autospec=True)
@mock.patch('subprocess.Popen', autospec=True, name='subprocess.Popen')
class TestSubprocessRunner(unittest.TestCase):
    @staticmethod
    def prepare_close(popen, stderr_val=None, ec=0):
        stdout_lines = [b' \n', b'2\n', b'3\n', b' \n']
        stderr_lines = (
            [b' \n', b'0\n', b'1\n', b' \n'] if stderr_val is None else []
        )
        mock_stdout_effect = []
        mock_stderr_effect = []
        mock_stdout_effect.extend(stdout_lines)
        mock_stderr_effect.extend(stderr_lines)
        mock_stdout_effect.extend([IOError] * 100)
        mock_stderr_effect.extend([IOError] * 100)
        stderr_readline = mock.Mock(side_effect=mock_stderr_effect)
        stdout_readline = mock.Mock(side_effect=mock_stdout_effect)

        stdout = mock.Mock()
        stderr = mock.Mock()

        stdout.attach_mock(stdout_readline, 'readline')
        stderr.attach_mock(stderr_readline, 'readline')

        popen_obj = mock.Mock()
        popen_obj.attach_mock(stdout, 'stdout')
        popen_obj.attach_mock(stderr, 'stderr')
        popen_obj.configure_mock(returncode=ec)

        popen.return_value = popen_obj

        # noinspection PyTypeChecker
        exp_result = exec_result.ExecResult(
            cmd=command,
            stderr=stderr_lines,
            stdout=stdout_lines,
            exit_code=ec
            )

        return popen_obj, exp_result

    def test_call(self, popen, fcntl, logger):
        popen_obj, exp_result = self.prepare_close(popen)

        runner = subprocess_runner.Subprocess()

        # noinspection PyTypeChecker
        result = runner.execute(command)
        self.assertEqual(
            result, exp_result

        )
        popen.assert_has_calls((
            mock.call(
                args=[command],
                cwd=None,
                env=None,
                shell=True,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                universal_newlines=False),
        ))
        logger.assert_has_calls((
            mock.call.debug(
                "Executing command: {!r}".format(command.rstrip())),
            mock.call.debug(
                '{cmd!r} execution results: Exit code: {code}'.format(
                    cmd=command,
                    code=result.exit_code
                )),
        ))
        self.assertIn(
            mock.call.poll(), popen_obj.mock_calls
        )

    def test_call_verbose(self, popen, fcntl, logger):
        _, _ = self.prepare_close(popen)

        runner = subprocess_runner.Subprocess()

        # noinspection PyTypeChecker
        result = runner.execute(command, verbose=True)

        logger.assert_has_calls((
            mock.call.debug(
                "Executing command: {!r}".format(command.rstrip())),
            mock.call.debug(
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
                )),
        ))


@mock.patch('devops.helpers.subprocess_runner.logger', autospec=True)
class TestSubprocessRunnerHelpers(unittest.TestCase):
    @mock.patch('devops.helpers.subprocess_runner.Subprocess.execute')
    def test_check_call(self, execute, logger):
        exit_code = 0
        return_value = {
            'stderr_str': '0\n1',
            'stdout_str': '2\n3',
            'exit_code': exit_code,
            'stderr': [b' \n', b'0\n', b'1\n', b' \n'],
            'stdout': [b' \n', b'2\n', b'3\n', b' \n']}
        execute.return_value = return_value

        verbose = False

        runner = subprocess_runner.Subprocess()

        # noinspection PyTypeChecker
        result = runner.check_call(
            command=command, verbose=verbose, timeout=None)
        execute.assert_called_once_with(command, verbose, None)
        self.assertEqual(result, return_value)

        exit_code = 1
        return_value['exit_code'] = exit_code
        execute.reset_mock()
        execute.return_value = return_value
        with self.assertRaises(error.DevopsCalledProcessError):
            # noinspection PyTypeChecker
            runner.check_call(command=command, verbose=verbose, timeout=None)
        execute.assert_called_once_with(command, verbose, None)

    @mock.patch('devops.helpers.subprocess_runner.Subprocess.execute')
    def test_check_call_expected(self, execute, logger):
        exit_code = 0
        return_value = {
            'stderr_str': '0\n1',
            'stdout_str': '2\n3',
            'exit_code': exit_code,
            'stderr': [b' \n', b'0\n', b'1\n', b' \n'],
            'stdout': [b' \n', b'2\n', b'3\n', b' \n']}
        execute.return_value = return_value

        verbose = False

        runner = subprocess_runner.Subprocess()

        # noinspection PyTypeChecker
        result = runner.check_call(
            command=command, verbose=verbose, timeout=None, expected=[0, 75])
        execute.assert_called_once_with(command, verbose, None)
        self.assertEqual(result, return_value)

        exit_code = 1
        return_value['exit_code'] = exit_code
        execute.reset_mock()
        execute.return_value = return_value
        with self.assertRaises(error.DevopsCalledProcessError):
            # noinspection PyTypeChecker
            runner.check_call(
                command=command, verbose=verbose, timeout=None,
                expected=[0, 75]
            )
        execute.assert_called_once_with(command, verbose, None)

    @mock.patch('devops.helpers.subprocess_runner.Subprocess.check_call')
    def test_check_stderr(self, check_call, logger):
        return_value = {
            'stderr_str': '',
            'stdout_str': '2\n3',
            'exit_code': 0,
            'stderr': [],
            'stdout': [b' \n', b'2\n', b'3\n', b' \n']}
        check_call.return_value = return_value

        verbose = False
        raise_on_err = True

        runner = subprocess_runner.Subprocess()

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
        with self.assertRaises(error.DevopsCalledProcessError):
            # noinspection PyTypeChecker
            runner.check_stderr(
                command=command, verbose=verbose, timeout=None,
                raise_on_err=raise_on_err)
        check_call.assert_called_once_with(
            command, verbose, timeout=None,
            error_info=None, raise_on_err=raise_on_err)
