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

import mock

from django.test import TestCase

from devops.models.node import Node


class MyNode(Node):

    def define(self):
        return super(MyNode, self).define()


class TestPrePostHook(TestCase):

    def setUp(self):
        super(TestPrePostHook, self).setUp()

        self.node = MyNode()

        self.node.ext.pre_define = mock.Mock(return_value=None)
        self.node.ext.post_define = mock.Mock(return_value=None)

        self.node.ext.pre_start = mock.Mock(return_value=None)
        self.node.ext.post_start = mock.Mock(return_value=None)

    def test_define(self):
        self.node.define()

        self.node.ext.pre_define.assert_called_once_with()
        self.node.ext.post_define.assert_called_once_with()

    def test_start(self):
        self.node.start()

        self.node.ext.pre_start.assert_called_once_with()
        self.node.ext.post_start.assert_called_once_with()

    def test_destroy(self):
        self.node.ext.post_destroy = mock.Mock(return_value=None)
        self.node.destroy()

        self.node.ext.post_destroy.assert_called_once_with()

        del self.node.ext.post_destroy
        self.node.ext.pre_destroy = mock.Mock(return_value=None)
        self.node.destroy()

        self.node.ext.pre_destroy.assert_called_once_with()

    def test_remove(self):
        self.node.save()

        self.node.ext.pre_remove = mock.Mock(return_value=None)
        self.node.ext.post_remove = mock.Mock(return_value=None)

        self.node.remove()

        self.node.ext.pre_remove.assert_called_once_with()
        self.node.ext.post_remove.assert_called_once_with()
