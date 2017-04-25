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

# pylint: disable=no-self-use

import collections
import os

from django.test import TestCase
import mock

from devops import error
from devops.helpers import templates


class TestTemplateLoader(TestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        self.open_mock = mock.mock_open(read_data='image_data')
        self.patch('devops.helpers.templates.open',
                   self.open_mock, create=True)
        self.os_mock = self.patch('devops.helpers.templates.os')
        self.isfiles = ['/path/to/my.yaml']
        self.os_mock.path.isfile.side_effect = self.isfiles.__contains__
        self.os_mock.path.dirname = os.path.dirname
        self.os_mock.path.join = os.path.join
        self.os_mock.path.split = os.path.split

        self.jpath_mock = self.patch('jinja2.loaders.path')
        self.jpath_mock.getmtime.return_value = 42
        self.jpath_mock.join.return_value = '/path/to/my.yaml'
        self.jpath_mock.sep = os.path.sep
        self.jpath_mock.altsep = os.path.altsep
        self.jpath_mock.pardir = os.path.pardir

    def test_not_file(self):
        with self.assertRaises(error.DevopsError):
            templates.yaml_template_load('/path/to/dir')

    def test_mapping_order(self):
        open_mock = mock.mock_open(
            read_data='mapping:\n'
                      '    one: 1\n'
                      '    two: 2\n'
                      '    three: 3\n')
        self.patch('jinja2.utils.open', open_mock, create=True)
        m = templates.yaml_template_load('/path/to/my.yaml')
        assert isinstance(m['mapping'], collections.OrderedDict)
        assert m['mapping'] == collections.OrderedDict([
            ('one', 1),
            ('two', 2),
            ('three', 3),
        ])

    def test_os_env_default(self):
        open_mock = mock.mock_open(
            read_data='env_value: !os_env MYVAR, 100\n')
        self.patch('jinja2.utils.open', open_mock, create=True)
        self.os_mock.environ = {}
        m = templates.yaml_template_load('/path/to/my.yaml')
        assert m['env_value'] == 100

    def test_jinja_os_env_default(self):
        open_mock = mock.mock_open(
            read_data='env_value: {{ os_env("MYVAR", 200) }}\n')
        self.patch('jinja2.utils.open', open_mock, create=True)

        self.os_mock.environ = {}
        m = templates.yaml_template_load('/path/to/my.yaml')
        assert m['env_value'] == 200

    def test_os_env(self):
        open_mock = mock.mock_open(
            read_data='env_value: !os_env MYVAR\n')
        self.patch('jinja2.utils.open', open_mock, create=True)
        self.os_mock.environ = {'MYVAR': '30'}
        m = templates.yaml_template_load('/path/to/my.yaml')
        assert m['env_value'] == 30

    def test_jinja_os_env(self):
        open_mock = mock.mock_open(
            read_data='env_value: {{ os_env("MYVAR") }}\n')
        self.patch('jinja2.utils.open', open_mock, create=True)
        self.os_mock.environ = {'MYVAR': '10.20.30.40/32'}
        m = templates.yaml_template_load('/path/to/my.yaml')
        assert m['env_value'] == '10.20.30.40/32'

    def test_os_env_required(self):
        open_mock = mock.mock_open(
            read_data='env_value: !os_env\n')
        self.patch('jinja2.utils.open', open_mock, create=True)
        self.os_mock.environ = {}
        with self.assertRaises(error.DevopsError):
            templates.yaml_template_load('/path/to/my.yaml')

    def test_os_env_no_value(self):
        open_mock = mock.mock_open(
            read_data='env_value: !os_env MYVAR\n')
        self.patch('jinja2.utils.open', open_mock, create=True)
        self.os_mock.environ = {}
        with self.assertRaises(error.DevopsError):
            templates.yaml_template_load('/path/to/my.yaml')

    def test_include(self):
        self.isfiles.append('/path/to/file2.yaml')
        mock_open1 = mock.mock_open(read_data='myinclude: !include file2.yaml')
        mock_open1.return_value.name = '/path/to/my.yaml'
        mock_open2 = mock.mock_open(read_data='10')
        mock_open2.return_value.name = '/path/to/file2.yaml'
        open_mock = self.patch(
            'jinja2.utils.open', new_callable=mock.mock_open, create=True)
        open_mock.side_effect = (
            mock_open1.return_value, mock_open2.return_value)

        m = templates.yaml_template_load('/path/to/my.yaml')
        assert m == {'myinclude': 10}

    def test_include_exception(self):
        mock_open1 = mock.mock_open(read_data='myinclude: !include file2.yaml')
        mock_open1.return_value.name = '/path/to/my.yaml'
        mock_open2 = mock.mock_open(read_data='10')
        mock_open2.return_value.name = '/path/to/file2.yaml'
        open_mock = self.patch(
            'jinja2.utils.open', new_callable=mock.mock_open, create=True)
        open_mock.side_effect = (
            mock_open1.return_value, mock_open2.return_value)

        with self.assertRaises(error.DevopsError):
            templates.yaml_template_load('/path/to/my.yaml')
