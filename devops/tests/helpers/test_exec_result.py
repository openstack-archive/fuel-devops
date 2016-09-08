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

# pylint: disable=no-self-use

from unittest import TestCase

import mock

from devops import error
from devops.helpers.exec_result import ExecResult
from devops.helpers.proc_enums import ExitCodes


cmd = 'ls -la'


# noinspection PyTypeChecker
class TestExecResult(TestCase):
    @mock.patch('devops.helpers.exec_result.logger')
    def test_create_minimal(self, logger):
        """Test defaults"""
        exec_result = ExecResult(cmd=cmd)
        self.assertEqual(exec_result.cmd, cmd)
        self.assertEqual(exec_result.cmd, exec_result['cmd'])
        self.assertEqual(exec_result.stdout, [])
        self.assertEqual(exec_result.stdout, exec_result['stdout'])
        self.assertEqual(exec_result.stderr, [])
        self.assertEqual(exec_result.stderr, exec_result['stderr'])
        self.assertEqual(exec_result.stdout_str, '')
        self.assertEqual(exec_result.stdout_str, exec_result['stdout_str'])
        self.assertEqual(exec_result.stderr_str, '')
        self.assertEqual(exec_result.stderr_str, exec_result['stderr_str'])
        self.assertEqual(exec_result.stdout_brief, '')
        self.assertEqual(exec_result.stdout_brief, exec_result['stdout_brief'])
        self.assertEqual(exec_result.stderr_brief, '')
        self.assertEqual(exec_result.stderr_brief, exec_result['stderr_brief'])
        self.assertEqual(exec_result.exit_code, ExitCodes.EX_INVALID)
        self.assertEqual(exec_result.exit_code, exec_result['exit_code'])
        self.assertEqual(
            repr(exec_result),
            '{cls}(cmd={cmd!r}, stdout={stdout}, stderr={stderr}, '
            'exit_code={exit_code!s})'.format(
                cls=ExecResult.__name__,
                cmd=cmd,
                stdout=[],
                stderr=[],
                exit_code=ExitCodes.EX_INVALID
            )
        )
        self.assertEqual(
            str(exec_result),
            "{cls}(\n\tcmd={cmd!r},"
            "\n\t stdout=\n'{stdout_brief}',"
            "\n\tstderr=\n'{stderr_brief}', "
            '\n\texit_code={exit_code!s}\n)'.format(
                cls=ExecResult.__name__,
                cmd=cmd,
                stdout_brief='',
                stderr_brief='',
                exit_code=ExitCodes.EX_INVALID
            )
        )

        with self.assertRaises(IndexError):
            # noinspection PyStatementEffect
            exec_result['nonexistent']

        with self.assertRaises(error.DevopsError):
            # noinspection PyStatementEffect
            exec_result['stdout_json']
        logger.assert_has_calls((
            mock.call.exception(
                "'{cmd}' stdout is not valid json:\n"
                "{stdout_str!r}\n".format(cmd=cmd, stdout_str='')),
        ))
        self.assertIsNone(exec_result['stdout_yaml'])

        self.assertEqual(
            hash(exec_result),
            hash((ExecResult, cmd, '', '', ExitCodes.EX_INVALID))
        )

    @mock.patch('devops.helpers.exec_result.logger', autospec=True)
    def test_not_implemented(self, logger):
        """Test assertion on non implemented deserializer"""
        exec_result = ExecResult(cmd=cmd)
        deserialize = getattr(exec_result, '_ExecResult__deserialize')
        with self.assertRaises(error.DevopsNotImplementedError):
            deserialize('tst')
        logger.assert_has_calls((
            mock.call.error(
                '{fmt} deserialize target is not implemented'.format(
                    fmt='tst')),
        ))

    def test_setters(self):
        exec_result = ExecResult(cmd=cmd)
        self.assertEqual(exec_result.exit_code, ExitCodes.EX_INVALID)
        exec_result.exit_code = 0
        self.assertEqual(exec_result.exit_code, 0)
        self.assertEqual(exec_result.exit_code, exec_result['exit_code'])

        tst_stdout = [
            b'Test\n',
            b'long\n',
            b'stdout\n',
            b'data\n',
            b' \n',
            b'5\n',
            b'6\n',
            b'7\n',
            b'8\n',
            b'end!\n'
        ]

        tst_stderr = [b'test\n'] * 10

        exec_result['stdout'] = tst_stdout
        self.assertEqual(exec_result.stdout, tst_stdout)
        self.assertEqual(exec_result.stdout, exec_result['stdout'])

        exec_result['stderr'] = tst_stderr
        self.assertEqual(exec_result.stderr, tst_stderr)
        self.assertEqual(exec_result.stderr, exec_result['stderr'])

        with self.assertRaises(TypeError):
            exec_result.exit_code = 'code'

        with self.assertRaises(error.DevopsError):
            exec_result['stdout_brief'] = 'test'

        with self.assertRaises(IndexError):
            exec_result['test'] = True

        with self.assertRaises(TypeError):
            exec_result.stdout = 'stdout'

        self.assertEqual(exec_result.stdout, tst_stdout)

        with self.assertRaises(TypeError):
            exec_result.stderr = 'stderr'

        self.assertEqual(exec_result.stderr, tst_stderr)

        stdout_br = tst_stdout[:3] + [b'...\n'] + tst_stdout[-3:]
        stderr_br = tst_stderr[:3] + [b'...\n'] + tst_stderr[-3:]

        stdout_brief = b''.join(stdout_br).strip().decode(encoding='utf-8')
        stderr_brief = b''.join(stderr_br).strip().decode(encoding='utf-8')

        self.assertEqual(exec_result.stdout_brief, stdout_brief)
        self.assertEqual(exec_result.stderr_brief, stderr_brief)

    def test_json(self):
        exec_result = ExecResult('test', stdout=[b'{"test": true}'])
        self.assertEqual(exec_result.stdout_json, {'test': True})

    @mock.patch('devops.helpers.exec_result.logger', autospec=True)
    def test_deprecations(self, logger):
        exec_result = ExecResult('test', stdout=[b'{"test": true}'])
        for deprecated in ('stdout_json', 'stdout_yaml'):
            exec_result['{}'.format(deprecated)] = {'test': False}
            logger.assert_has_calls((
                mock.call.warning(
                    '{key} is read-only and calculated automatically'.format(
                        key='{}'.format(deprecated)
                    )),
            ))
            self.assertEqual(exec_result[deprecated], {'test': True})
            logger.reset_mock()
