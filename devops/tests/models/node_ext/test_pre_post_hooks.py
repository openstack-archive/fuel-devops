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

from devops.tests.driver.driverless import DriverlessTestCase


class TestPrePostHook(DriverlessTestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        super(TestPrePostHook, self).setUp()

        self.ext_cls_mock = self.patch(
            'devops.models.node_ext.default.NodeExtension', autospec=True)
        self.ext_mock = self.ext_cls_mock.return_value

        self.node = self.group.add_node(name='test-node', role='default')
        assert self.node.ext is self.ext_mock

        self.ext_mock.pre_define = mock.Mock(return_value=None)
        self.ext_mock.post_define = mock.Mock(return_value=None)

        self.ext_mock.pre_start = mock.Mock(return_value=None)
        self.ext_mock.post_start = mock.Mock(return_value=None)

    def test_define(self):
        self.node.define()

        self.ext_mock.pre_define.assert_called_once_with()
        self.ext_mock.post_define.assert_called_once_with()

    def test_start(self):
        self.node.start()

        self.ext_mock.pre_start.assert_called_once_with()
        self.ext_mock.post_start.assert_called_once_with()

    def test_destroy(self):
        self.ext_mock.post_destroy = mock.Mock(return_value=None)
        self.node.destroy()

        self.ext_mock.post_destroy.assert_called_once_with()

        del self.ext_mock.post_destroy
        self.ext_mock.pre_destroy = mock.Mock(return_value=None)
        self.node.destroy()

        self.ext_mock.pre_destroy.assert_called_once_with()

    def test_remove(self):
        self.node.save()

        self.ext_mock.pre_remove = mock.Mock(return_value=None)
        self.ext_mock.post_remove = mock.Mock(return_value=None)

        self.node.remove()

        self.ext_mock.pre_remove.assert_called_once_with()
        self.ext_mock.post_remove.assert_called_once_with()
