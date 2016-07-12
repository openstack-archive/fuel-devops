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

from devops.helpers.exec_result import DevopsError
from devops.helpers.exec_result import DevopsNotImplementedError
from devops.helpers.exec_result import ExecResult


cmd = 'ls -la'


# noinspection PyTypeChecker
class TestExecResult(TestCase):
    @mock.patch('devops.helpers.exec_result.logger', autospec=True)
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
        self.assertEqual(exec_result.exit_code, -1)
        self.assertEqual(exec_result.exit_code, exec_result['exit_code'])
        self.assertEqual(
            repr(exec_result),
            '{cls}(cmd={cmd}, stdout={stdout}, stderr={stderr}, '
            'exit_code={exit_code})'.format(
                cls=ExecResult.__name__,
                cmd=cmd,
                stdout=[],
                stderr=[],
                exit_code=-1
            )
        )
        self.assertEqual(
            str(exec_result),
            '{cls}(cmd={cmd}, stdout={stdout_brief}, stderr={stderr_brief}, '
            'exit_code={exit_code})'.format(
                cls=ExecResult.__name__,
                cmd=cmd,
                stdout_brief='',
                stderr_brief='',
                exit_code=-1
            )
        )

        with self.assertRaises(IndexError):
            exec_result['nonexistent']

        with self.assertRaises(DevopsError):
            exec_result['json']
        logger.assert_has_calls((
            mock.call.exception(
                "'{cmd}' stdout is not valid json:\n"
                "{stdout_str!r}\n".format(cmd=cmd, stdout_str='')),
        ))
        self.assertIsNone(exec_result['yaml'])

        self.assertEqual(
            hash(exec_result),
            hash((ExecResult, cmd, '', '', -1))
        )

    @mock.patch('devops.helpers.exec_result.logger', autospec=True)
    def test_not_implemented(self, logger):
        """Test assertion on non implemented deserializer"""
        exec_result = ExecResult(cmd=cmd)
        deserialize = getattr(exec_result, '_ExecResult__deserialize')
        with self.assertRaises(DevopsNotImplementedError):
            deserialize('tst')
        logger.assert_has_calls((
            mock.call.error(
                '{fmt} deserialize target is not implemented'.format(
                    fmt='tst')),
        ))

    def test_setters(self):
        exec_result = ExecResult(cmd=cmd)
        self.assertEqual(exec_result.exit_code, -1)
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

        with self.assertRaises(DevopsError):
            exec_result['stdout_str'] = 'test'

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
        self.assertEqual(exec_result.json, {'test': True})
