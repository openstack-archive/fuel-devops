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


from devops.tests.driver.driverless import DriverlessTestCase


class TestCustomNodeRole(DriverlessTestCase):

    def setUp(self):
        super(TestCustomNodeRole, self).setUp()

        self.node = self.group.add_node(
            name='test-node',
            role='my_custom_role')

    def test_custom_role(self):
        self.node.define()
        self.node.start()
        self.node.destroy()
        self.node.remove()

    def test_custom_role_ext(self):
        assert self.node.ext is None
