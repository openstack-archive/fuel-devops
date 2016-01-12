#    Copyright 2015 Mirantis, Inc.
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

import os

import mock
from django.test import TestCase

from devops import TEMPLATES_DIR
from devops.helpers import template_validator
from devops.helpers.templates import yaml_template_load


class TestDefaultTemplate(TestCase):

    def test_template(self):
        tmpl_path = os.path.join(TEMPLATES_DIR, 'default.yaml')
        mock_env = dict(
            ENV_NAME='test_env',
            ISO_PATH='/tmp/my.iso',
        )
        with mock.patch.dict('os.environ', mock_env):
            tmpl = yaml_template_load(tmpl_path)
        assert template_validator.validate(tmpl)
