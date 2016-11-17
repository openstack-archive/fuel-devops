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

import unittest

import mock

from devops import error
from devops.helpers import exec_result
from devops.helpers.proc_enums import ExitCodes


cmd = 'ls -la'


# noinspection PyTypeChecker
class TestExecResult(unittest.TestCase):
    @mock.patch('devops.helpers.exec_result.logger')
    def test_create_minimal(self, logger):
        """Test defaults"""
        result = exec_result.ExecResult(cmd=cmd)
        self.assertEqual(result.cmd, cmd)
        self.assertEqual(result.cmd, result['cmd'])
        self.assertEqual(result.stdout, [])
        self.assertEqual(result.stdout, result['stdout'])
        self.assertEqual(result.stderr, [])
        self.assertEqual(result.stderr, result['stderr'])
        self.assertEqual(result.stdout_bin, bytearray())
        self.assertEqual(result.stderr_bin, bytearray())
        self.assertEqual(result.stdout_str, '')
        self.assertEqual(result.stdout_str, result['stdout_str'])
        self.assertEqual(result.stderr_str, '')
        self.assertEqual(result.stderr_str, result['stderr_str'])
        self.assertEqual(result.stdout_brief, '')
        self.assertEqual(result.stdout_brief, result['stdout_brief'])
        self.assertEqual(result.stderr_brief, '')
        self.assertEqual(result.stderr_brief, result['stderr_brief'])
        self.assertEqual(result.exit_code, ExitCodes.EX_INVALID)
        self.assertEqual(result.exit_code, result['exit_code'])
        self.assertEqual(
            repr(result),
            '{cls}(cmd={cmd!r}, stdout={stdout}, stderr={stderr}, '
            'exit_code={exit_code!s})'.format(
                cls=exec_result.ExecResult.__name__,
                cmd=cmd,
                stdout=[],
                stderr=[],
                exit_code=ExitCodes.EX_INVALID
            )
        )
        self.assertEqual(
            str(result),
            "{cls}(\n\tcmd={cmd!r},"
            "\n\t stdout=\n'{stdout_brief}',"
            "\n\tstderr=\n'{stderr_brief}', "
            '\n\texit_code={exit_code!s}\n)'.format(
                cls=exec_result.ExecResult.__name__,
                cmd=cmd,
                stdout_brief='',
                stderr_brief='',
                exit_code=ExitCodes.EX_INVALID
            )
        )

        with self.assertRaises(IndexError):
            # pylint: disable=pointless-statement
            # noinspection PyStatementEffect
            result['nonexistent']
            # pylint: enable=pointless-statement

        with self.assertRaises(error.DevopsError):
            # pylint: disable=pointless-statement
            # noinspection PyStatementEffect
            result['stdout_json']
            # pylint: enable=pointless-statement
        logger.assert_has_calls((
            mock.call.exception(
                " stdout is not valid json:\n"
                "{stdout_str!r}\n".format(stdout_str='')),
        ))
        self.assertIsNone(result['stdout_yaml'])

        self.assertEqual(
            hash(result),
            hash((exec_result.ExecResult, cmd, '', '', ExitCodes.EX_INVALID))
        )

    @mock.patch('devops.helpers.exec_result.logger', autospec=True)
    def test_not_implemented(self, logger):
        """Test assertion on non implemented deserializer"""
        result = exec_result.ExecResult(cmd=cmd)
        deserialize = getattr(result, '_ExecResult__deserialize')
        with self.assertRaises(error.DevopsNotImplementedError):
            deserialize('tst')
        logger.assert_has_calls((
            mock.call.error(
                '{fmt} deserialize target is not implemented'.format(
                    fmt='tst')),
        ))

    def test_setters(self):
        result = exec_result.ExecResult(cmd=cmd)
        self.assertEqual(result.exit_code, ExitCodes.EX_INVALID)
        result.exit_code = 0
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.exit_code, result['exit_code'])

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

        result['stdout'] = tst_stdout
        self.assertEqual(result.stdout, tst_stdout)
        self.assertEqual(result.stdout, result['stdout'])

        result['stderr'] = tst_stderr
        self.assertEqual(result.stderr, tst_stderr)
        self.assertEqual(result.stderr, result['stderr'])

        with self.assertRaises(TypeError):
            result.exit_code = 'code'

        with self.assertRaises(error.DevopsError):
            result['stdout_brief'] = 'test'

        with self.assertRaises(IndexError):
            result['test'] = True

        with self.assertRaises(TypeError):
            result.stdout = 'stdout'

        self.assertEqual(result.stdout, tst_stdout)

        with self.assertRaises(TypeError):
            result.stderr = 'stderr'

        self.assertEqual(result.stderr, tst_stderr)

        self.assertEqual(result.stdout_bin, bytearray(b''.join(tst_stdout)))
        self.assertEqual(result.stderr_bin, bytearray(b''.join(tst_stderr)))

        stdout_br = tst_stdout[:3] + [b'...\n'] + tst_stdout[-3:]
        stderr_br = tst_stderr[:3] + [b'...\n'] + tst_stderr[-3:]

        stdout_brief = b''.join(stdout_br).strip().decode(encoding='utf-8')
        stderr_brief = b''.join(stderr_br).strip().decode(encoding='utf-8')

        self.assertEqual(result.stdout_brief, stdout_brief)
        self.assertEqual(result.stderr_brief, stderr_brief)

    def test_json(self):
        result = exec_result.ExecResult('test', stdout=[b'{"test": true}'])
        self.assertEqual(result.stdout_json, {'test': True})

    @mock.patch('devops.helpers.exec_result.logger', autospec=True)
    def test_deprecations(self, logger):
        result = exec_result.ExecResult('test', stdout=[b'{"test": true}'])
        for deprecated in ('stdout_json', 'stdout_yaml'):
            result['{}'.format(deprecated)] = {'test': False}
            logger.assert_has_calls((
                mock.call.warning(
                    '{key} is read-only and calculated automatically'.format(
                        key='{}'.format(deprecated)
                    )),
            ))
            self.assertEqual(result[deprecated], {'test': True})
            logger.reset_mock()
