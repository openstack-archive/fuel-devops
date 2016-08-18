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

from json import loads
from threading import RLock

from yaml import safe_load

from devops.error import DevopsError
from devops.error import DevopsNotImplementedError
from devops.helpers.proc_enums import ExitCodes
from devops import logger


deprecated_aliases = {
    'stdout_str',
    'stderr_str',
    'stdout_json',
    'stdout_yaml'
}


class ExecResult(object):
    __slots__ = [
        '__cmd', '__stdout', '__stderr', '__exit_code',
        '__stdout_str', '__stderr_str', '__stdout_brief', '__stderr_brief',
        '__stdout_json', '__stdout_yaml',
        '__lock'
    ]

    def __init__(self, cmd, stdout=None, stderr=None,
                 exit_code=ExitCodes.EX_INVALID):
        """Command execution result read from fifo

        :type cmd: str
        :type stdout: list
        :type stderr: list
        :type exit_code: ExitCodes
        """
        self.__lock = RLock()

        self.__cmd = cmd
        self.__stdout = stdout if stdout is not None else []
        self.__stderr = stderr if stderr is not None else []

        self.__exit_code = None
        self.exit_code = exit_code

        # By default is none:
        self.__stdout_str = None
        self.__stderr_str = None
        self.__stdout_brief = None
        self.__stderr_brief = None

        self.__stdout_json = None
        self.__stdout_yaml = None

    @property
    def lock(self):
        """Lock object for thread-safe operation

        :rtype: RLock
        """
        return self.__lock

    @staticmethod
    def _get_str_from_list(src):
        """Join data in list to the string, with python 2&3 compatibility.

        :type src: list
        :rtype: str
        """
        return b''.join(src).strip().decode(encoding='utf-8')

    @classmethod
    def _get_brief(cls, data):
        """Get brief output: 7 lines maximum (3 first + ... + 3 last)

        :type data: list
        :rtype: str
        """
        if len(data) <= 7:
            return cls._get_str_from_list(data)
        else:
            return cls._get_str_from_list(
                data[:3] + [b'...\n'] + data[-3:]
            )

    @property
    def cmd(self):
        """Executed command

        :rtype: str
        """
        return self.__cmd

    @property
    def stdout(self):
        """Stdout output as list of binaries

        :rtype: list
        """
        return self.__stdout

    @stdout.setter
    def stdout(self, new_val):
        """Stdout output as list of binaries

        :type new_val: list
        :raises: TypeError
        """
        if not isinstance(new_val, (list, type(None))):
            raise TypeError('stdout should be list only!')
        with self.lock:
            self.__stdout_str = None
            self.__stdout_brief = None
            self.__stdout_json = None
            self.__stdout_yaml = None
            self.__stdout = new_val

    @property
    def stderr(self):
        """Stderr output as list of binaries

        :rtype: list
        """
        return self.__stderr

    @stderr.setter
    def stderr(self, new_val):
        """Stderr output as list of binaries

        :type new_val: list
        :raises: TypeError
        """
        if not isinstance(new_val, (list, None)):
            raise TypeError('stderr should be list only!')
        with self.lock:
            self.__stderr_str = None
            self.__stderr_brief = None
            self.__stderr = new_val

    @property
    def stdout_str(self):
        """Stdout output as string

        :rtype: str
        """
        with self.lock:
            if self.__stdout_str is None:
                self.__stdout_str = self._get_str_from_list(self.stdout)
            return self.__stdout_str

    @property
    def stderr_str(self):
        """Stderr output as string

        :rtype: str
        """
        with self.lock:
            if self.__stderr_str is None:
                self.__stderr_str = self._get_str_from_list(self.stderr)
            return self.__stderr_str

    @property
    def stdout_brief(self):
        """Brief stdout output (mostly for exceptions)

        :rtype: str
        """
        with self.lock:
            if self.__stdout_brief is None:
                self.__stdout_brief = self._get_brief(self.stdout)
            return self.__stdout_brief

    @property
    def stderr_brief(self):
        """Brief stderr output (mostly for exceptions)

        :rtype: str
        """
        with self.lock:
            if self.__stderr_brief is None:
                self.__stderr_brief = self._get_brief(self.stderr)
            return self.__stderr_brief

    @property
    def exit_code(self):
        """Return(exit) code of command

        :rtype: int
        """
        return self.__exit_code

    @exit_code.setter
    def exit_code(self, new_val):
        """Return(exit) code of command

        :type new_val: int
        """
        if not isinstance(new_val, (int, ExitCodes)):
            raise TypeError('Exit code is strictly int')
        with self.lock:
            if isinstance(new_val, int) and \
                    new_val in ExitCodes.__members__.values():
                new_val = ExitCodes(new_val)
            self.__exit_code = new_val

    def __deserialize(self, fmt):
        """Deserialize stdout as data format

        :type fmt: str
        :rtype: object
        :raises: DevopsError
        """
        try:
            if fmt == 'json':
                return loads(self.stdout_str, encoding='utf-8')
            elif fmt == 'yaml':
                return safe_load(self.stdout_str)
        except BaseException:
            tmpl = (
                "'{cmd}' stdout is not valid {fmt}:\n"
                '{{stdout!r}}\n'.format(
                    cmd=self.cmd,
                    fmt=fmt))
            logger.exception(tmpl.format(stdout=self.stdout_str))
            raise DevopsError(tmpl.format(stdout=self.stdout_brief))
        msg = '{fmt} deserialize target is not implemented'.format(fmt=fmt)
        logger.error(msg)
        raise DevopsNotImplementedError(msg)

    @property
    def stdout_json(self):
        """JSON from stdout

        :rtype: object
        """
        with self.lock:
            if self.__stdout_json is None:
                # noinspection PyTypeChecker
                self.__stdout_json = self.__deserialize(fmt='json')
            return self.__stdout_json

    @property
    def stdout_yaml(self):
        """YAML from stdout

        :rtype: object
        """
        with self.lock:
            if self.__stdout_yaml is None:
                # noinspection PyTypeChecker
                self.__stdout_yaml = self.__deserialize(fmt='yaml')
            return self.__stdout_yaml

    @staticmethod
    def __dir__():
        return [
            'cmd', 'stdout', 'stderr', 'exit_code',
            'stdout_str', 'stderr_str', 'stdout_brief', 'stderr_brief',
            'stdout_json', 'stdout_yaml',
            'lock'
        ]

    def __getitem__(self, item):
        if item in dir(self):
            return getattr(self, item)
        raise IndexError(
            '"{item}" not found in {dir}'.format(
                item=item, dir=dir(self)
            )
        )

    def __setitem__(self, key, value):
        rw = ['stdout', 'stderr', 'exit_code']
        if key in rw:
            setattr(self, key, value)
            return
        if key in deprecated_aliases:
            logger.warning(
                '{key} is read-only and calculated automatically'.format(
                    key=key
                )
            )
            return
        if key in dir(self):
            raise DevopsError(
                '{key} is read-only!'.format(key=key)
            )
        raise IndexError(
            '{key} not found in {dir}'.format(
                key=key, dir=rw
            )
        )

    def __repr__(self):
        return (
            '{cls}(cmd={cmd}, stdout={stdout}, stderr={stderr}, '
            'exit_code={exit_code!s})'.format(
                cls=self.__class__.__name__,
                cmd=self.cmd,
                stdout=self.stdout,
                stderr=self.stderr,
                exit_code=self.exit_code
            ))

    def __str__(self):
        return (
            "{cls}(\n\tcmd={cmd},"
            "\n\t stdout=\n'{stdout_brief}',"
            "\n\tstderr=\n'{stderr_brief}', "
            '\n\texit_code={exit_code!s}\n)'.format(
                cls=self.__class__.__name__,
                cmd=self.cmd,
                stdout_brief=self.stdout_brief,
                stderr_brief=self.stderr_brief,
                exit_code=self.exit_code
            )
        )

    def __eq__(self, other):
        return all(
            (
                getattr(self, val) == getattr(other, val)
                for val in ['cmd', 'stdout', 'stderr', 'exit_code']
            )
        )

    def __hash__(self):
        return hash(
            (
                self.__class__, self.cmd, self.stdout_str, self.stderr_str,
                self.exit_code
            ))
