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

from devops.models import Environment
from django.test import TestCase


class TestIpmiNode(TestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        super(TestIpmiNode, self).setUp()

        # Create Environment
        self.ipmiclient_mock = self.patch(
            'devops.driver.baremetal.ipmi_driver.IpmiClient', autospec=True)
        self.ipmiclient = self.ipmiclient_mock.return_value
        self.wait_mock = self.patch(
            'devops.driver.baremetal.ipmi_driver.wait')

        self.env = Environment.create('test_env')
        self.group = self.env.add_group(
            group_name='test_group',
            driver_name='devops.driver.baremetal',
        )

        self.ap = self.env.add_address_pool(
            name='test_ap',
            net='172.0.0.0/16:24',
            tag=0,
            ip_reserved=dict(l2_network_device=1),
        )

        self.net_pool = self.group.add_network_pool(
            name='fuelweb_admin',
            address_pool_name='test_ap',
        )

        self.l2_net_dev = self.group.add_l2_network_device(
            name='test_l2_net_dev',
            address_pool='test_ap',
        )

        self.node = self.group.add_node(
            name='test_node',
            role='default',
            boot='pxe',
            force_set_boot=True,
            ipmi_user='user1',
            ipmi_password='pass1',
            ipmi_previlegies='OPERATOR',
            ipmi_host='ipmi-1.hostaddress.net',
            ipmi_lan_interface='lanplus',
            ipmi_port=623,
        )

    def test_define(self):
        self.node.define()

    def test_is_active(self):
        self.ipmiclient.power_status.return_value = 0

        assert self.node.is_active()

    def test_is_active_false(self):
        self.ipmiclient.power_status.return_value = 1

        assert self.node.is_active() is False

    def test_exists(self):
        self.ipmiclient.check_remote_host.return_value = True

        assert self.node.exists()

        self.ipmiclient.check_remote_host.assert_called_once_with()

    def test_start(self):
        self.ipmiclient.power_status.return_value = 1

        self.node.start()

        self.ipmiclient.assert_has_calls((
            mock.call.chassis_set_boot('pxe'),
            mock.call.power_status(),
            mock.call.power_on(),
        ))

    def test_restart(self):
        self.ipmiclient.power_status.return_value = 0

        self.node.start()

        self.ipmiclient.assert_has_calls((
            mock.call.chassis_set_boot('pxe'),
            mock.call.power_status(),
            mock.call.power_reset(),
        ))
        self.wait_mock.assert_called_once_with(
            self.node.is_active,
            timeout=60,
            timeout_msg="Node test_node / ipmi-1.hostaddress.net wasn't "
                        "started in 60 sec")

    def test_destroy(self):
        self.ipmiclient.power_status.return_value = 0

        self.node.destroy()

        self.ipmiclient.power_off.assert_called_once_with()
        assert self.wait_mock.called

    def test_remove(self):
        self.ipmiclient.power_status.return_value = 0

        self.node.remove()

        self.ipmiclient.assert_has_calls((
            mock.call.power_status(),
            mock.call.power_off(),
        ))
        assert self.wait_mock.called

    def test_reset(self):
        self.node.reset()

        self.ipmiclient.power_reset.assert_called_once_with()

    def test_reboot(self):
        self.node.reboot()

        self.ipmiclient.power_reset.assert_called_once_with()

    def test_shutdown(self):
        self.node.shutdown()

        self.ipmiclient.power_off.assert_called_once_with()
        assert self.wait_mock.called
