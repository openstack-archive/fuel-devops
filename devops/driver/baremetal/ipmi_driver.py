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

import uuid

from django.utils.functional import cached_property

from devops.driver.baremetal.ipmi_client import IpmiClient
from devops.helpers.helpers import wait
from devops.models.base import ParamField
from devops.models.driver import Driver
from devops.models.network import L2NetworkDevice
from devops.models.node import Node
from devops.models.volume import Volume


class IpmiDriver(Driver):
    """Driver params from template. keep in DB"""
    pass


class IpmiL2NetworkDevice(L2NetworkDevice):
    """L2NetworkDevice params from template. keep in DB"""
    pass


class IpmiVolume(Volume):
    """Volume params from template"""
    pass


class IpmiNode(Node):
    """IPMI Node

        Intel IPMI specification:
        http://www.intel.ru/content/dam/www/public/us/en/documents/
        product-briefs/ipmi-second-gen-interface-spec-v2-rev1-1.pdf

        The Node shall provide ability to manage remote
        baremetal node through ipmi interface by using
        ipmitool: http://sourceforge.net/projects/ipmitool/
        Take into account that it is suitable tool
        according to licence criteria.
        More info can be found here:
        http://ipmiutil.sourceforge.net/docs/ipmisw-compare.htm

        Note:
        Power management - on/off/reset
        User management - user list
        Chassis management - chassis info
        Virtual Storage management - ISO attache
        Sensors management - get sensors info
        Node management - start/stop/reset

        :param ipmi_user: str - the user login for IPMI board
        :param ipmi_password: str - the user password
        :param ipmi_previlegies: str - the user privileges level (OPERATOR)
        :param ipmi_host: str - remote host name
        :param ipmi_port: int - remote port number
        :param ipmi_lan_interface: str - the lan interface (lan, lanplus)
    """

    uuid = ParamField()  # LEGACY, for compatibility reason
    boot = ParamField(default='pxe')
    ipmi_user = ParamField()
    ipmi_password = ParamField()
    ipmi_previlegies = ParamField(default='OPERATOR')
    ipmi_host = ParamField()
    ipmi_lan_interface = ParamField(default="lanplus")
    ipmi_port = ParamField(default=623)

    @cached_property
    def conn(self):
        """Connection to libvirt api"""
        return IpmiClient(self.ipmi_user, self.ipmi_password, self.ipmi_host,
                          self.ipmi_previlegies, self.ipmi_lan_interface,
                          self.ipmi_port, self.name)

    def exists(self):
        """Check if node exists

        :param: None
        :return: bool - True if successful, False otherwise
        """
        return self.conn.check_remote_host()

    def is_active(self):
        """Check if node is active

        Note: we have to check power on and
              we have take into account that OS is working on remote host
        TODO: let's double check remote OS despite power is on

        :param: None
        :return: bool - True if successful, False otherwise.
        """
        return (0 == self.conn.power_status())

    def define(self):
        """Prepare node to start

        TODO: Mount ISO
        TODO: Set boot device
        Note: need to set boot device at first. Create record in DB
        """
        self.uuid = uuid.uuid4()
        super(IpmiNode, self).define()

    def start(self):
        """Node start. Power on """

        # Boot device is not stored in bios, so it should
        # be set every time when node starts.
        self.conn.chassis_set_boot('pxe')

        if self.is_active():
            # Re-start active node
            self.reboot()
        else:
            self.conn.power_on()
        wait(self.is_active, timeout=60,
             timeout_msg="Node {0} / {1} wasn't started in 60 sec".
             format(self.name, self.ipmi_host))

    def create(self):
        """Node creating. Create env but don't power on after """
        self.save()

    def destroy(self):
        """Node destroy. Power off """
        self.conn.power_off()
        wait(lambda: not self.is_active(), timeout=60,
             timeout_msg="Node {0} / {1} wasn't stopped in 60 sec".
             format(self.name, self.ipmi_host))

    def erase(self):
        """Node erase. Power off """
        super(IpmiNode, self).delete()
        if self.is_active():
            self.conn.power_off()

    def remove(self):
        """Node remove. Power off """
        self.conn.power_off()

    def reset(self):
        """Node reset. Power reset """
        self.conn.power_reset()

    def reboot(self):
        """Node reboot. Power reset """
        self.conn.power_reset()

    def shutdown(self):
        """Shutdown Node """
        self.conn.power_off()
