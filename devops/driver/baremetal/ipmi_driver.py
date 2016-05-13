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

import subprocess
import uuid

from django.utils.functional import cached_property

from devops.error import DevopsError
from devops.helpers.helpers import wait
from devops import logger
from devops.models.base import ParamField
from devops.models.driver import Driver
from devops.models.network import L2NetworkDevice
from devops.models.node import Node
from devops.models.volume import Volume


class IpmiClient(object):
    """IPMI client shall ensure connection with IPMI """

    def __init__(self, user, password, remote_host,
                 level='OPERATOR',
                 remote_lan_interface='lanplus',
                 remote_port=None, nodename=None):
        """init

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param remote_host: str - remote host name
        :param level: str - the user privileges level. (default OPERATOR)
               values: CALLBACK, USER, OPERATOR, ADMINISTRATOR, OEM, NO ACCESS
        :param remote_lan_interface: str - the lan interface
               values: (default 'lanplus'), lan, lanplus
        :param remote_port: int - remote port number
        :param nodename: str - node name
        :return: None
        """
        self.user = user
        self.password = password
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.remote_lan_interface = remote_lan_interface
        self.level = level
        self.nodename = nodename
        self.features = {
            'PowerManagement': ['status', 'on', 'off',
                                'cycle', 'reset', 'diag', 'soft'],
            'PowerManagementStatus': ['Chassis Power is on',
                                      'Chassis Power is off'],
            'PowerManagementOn': 'Chassis Power Control: Up/On',
            'PowerManagementOff': 'Chassis Power Control: Down/Off',
            'PowerManagementReset': 'Chassis Power Control: Reset',
            'PowerManagementCycle': 'Chassis Power Control: Cycle',
            'UserManagement': ['list'],
            'UserManagementPrivilegesLevel': {
                '1': 'CALLBACK',
                '2': 'USER',
                '3': 'OPERATOR',
                '4': 'ADMINISTRATOR',
                '5': 'OEM',
                '15': 'NO ACCESS'},
            'UserManagementListReply': 'ID  Name',
            'ChassisManagement': ['status', 'power', 'identify',
                                  'bootdev', 'bootparam', 'selftest'],
            'ChassisBootManagement': ['none', 'pxe', 'disk',
                                      'cdrom', 'bios', 'floppy',
                                      'safe', 'diag'],
            'ChassisSetBootDevice': 'Set Boot Device to cdrom',
            'LanManagement': ['print', 'stats get'],
            'ControllerManagement': ['info', 'getsysinfo',
                                     'getenables'],
            'VirtualStorageManagement': [],
            'SensorsManagement': []}
        self.userid = self.get_user_id()

    def __run_ipmi(self, cmd):
        """Run command through ipmitool

        :param cmd: list - ipmi command
        :return: object - data if successful, None otherwise
        """

        try:
            ipmitool_cmd = subprocess.check_output(["which",
                                                    "ipmitool"]).strip()
            if not ipmitool_cmd:
                raise DevopsError('ipmitool not found')
        except Exception:
            raise DevopsError('Node:{} ipmi_host:{} '
                              'ipmitool has not installed.\
                               No chance to go over'.format(self.nodename,
                                                            self.remote_host))
        ipmi_cmd_dict = {'ipmitool': ipmitool_cmd,
                         'remote_lan_interface': self.remote_lan_interface,
                         'remote_host': self.remote_host,
                         'remote_port': self.remote_port,
                         'user': self.user,
                         'password': self.password,
                         'level': self.level,
                         'cmd': cmd}
        lerrors = [(key, value) for (key, value) in ipmi_cmd_dict.items()
                   if value is None]
        if lerrors:
            raise DevopsError('Node:{} ipmi_host:{} '
                              'ipmitool arguments '
                              'key={}, value={}'
                              'are not valid'.format(self.nodename,
                                                     self.remote_host,
                                                     lerrors[0],
                                                     lerrors[1]))
        ipmi_cmd = [ipmitool_cmd,
                    '-I', self.remote_lan_interface,
                    '-H', self.remote_host,
                    '-U', self.user,
                    '-P', self.password,
                    '-L', self.level,
                    '-p', str(self.remote_port)]

        if isinstance(cmd, list):
            ipmi_cmd.extend(cmd)
        else:
            # workaround for commands like "stats get"
            args = " ".join(cmd).split(" ")
            ipmi_cmd.extend(args)

        out = None
        err = None
        code = None
        args = " ".join(ipmi_cmd).split(" ")

        try:
            # let's break down it again and prepare args
            pipe = subprocess.Popen(args,
                                    stderr=subprocess.PIPE,
                                    stdout=subprocess.PIPE)
            out, err = pipe.communicate()
            code = pipe.returncode
        except Exception as message:
            logger.debug('{}'.format(message))
            raise DevopsError('Node:{} Remote:{} ipmitool command [{}] '
                              'has failed with'
                              ' the exception: {}'.format(self.nodename,
                                                          self.remote_host,
                                                          cmd, message))

        if (out is None) or code != 0:
            logger.debug("rcode ={} or err ={}".format(code, err))
            raise DevopsError('Node:{} Remote:{} ipmitool command [{}] '
                              'has failed with the message: {}'
                              .format(self.nodename, self.remote_host, cmd, err))
        return out

    def __convert2dict(self, data):
        """Convert data output to dict

        :param data: str - ipmi command output
        :return: dict if OK, {} otherwise
        """
        res = {}
        if data:
            for i in data.split('\n'):
                if i:
                    key, value = map(str.strip, i.split(':'))
                    res.update({key: value})
        return res

    def __controller_management(self, command):
        """Try to do user controller

        :param command: str - ipmitool command string acceptable for 'power'
        :return: object - output if successful, empty string otherwise
        """
        if command in self.features.get('ControllerManagement'):
            return self.__run_ipmi(['mc', command])
        return ''

    def controller_info(self):
        """Try to controller status

        :param: None
        :return: dict - dict object if successful, {} otherwise
        """
        out = self.__controller_management('info')
        return self.__convert2dict(out)

    def check_remote_host(self):
        """Check baremetal node through ipmi

        :param: None
        :return: bool - True if successful, False otherwise
        """
        return self.controller_info() != {}

    def __user_management(self, command):
        """Try to do user management

        :param command: str - ipmitool command string acceptable for 'power'
        :return: object - output if successful, empty string otherwise
        """
        if command in self.features.get('UserManagement'):
            return self.__run_ipmi(['user', command])
        return ''

    def user_list(self):
        """Try to user list

        :param: None
        :return: list - list object if successful, [] otherwise
        """
        res = []
        out = self.__user_management('list')
        if out.find(self.features.get('UserManagementListReply')) is not None:
            # let's get user ID and Privileges. UserID is a first column
            userlist = out.strip().split('\n')
            for i in userlist[1:]:
                tstr = i.split(' ')
                idn, priv, name = tstr[0], tstr[-1], " ".join(
                    [value for value in tstr[1:4] if value])
                res.append({'id': idn, 'name': name, 'priv': priv})
        return res

    def get_user_id(self, user=None):
        """Get user id

        :param: None
        :return: id if successful, None otherwise.
        """
        for i in self.user_list():
            if user:
                if user == i.get('name'):
                    return i.get('id')
            else:
                if self.user == i.get('name'):
                    return i.get('id')
        return None

    def __power_management(self, command):
        """Try to do power management. status/on/off/reset

        :param command: str - ipmitool command string acceptable for 'power'
        :return: object - output if successful, empty string otherwise
        """
        if command in self.features.get('PowerManagement'):
            return self.__run_ipmi(['power', command])
        return ''

    def power_status(self):
        """Try to get power status

        :param: None
        :return: 1 - power on, 0 - power off, None otherwise.
        """
        out = self.__power_management('status').strip()
        if out.find(self.features.get('PowerManagementStatus', [])[0]):
            return 1
        elif out.find(self.features.get('PowerManagementStatus', [])[1]):
            return 0
        return None

    def power_on(self):
        """Try to power on

        :param: None
        :return: bool - True if successful, False otherwise
        """
        out = self.__power_management('on').strip()
        if out.find(self.features.get('PowerManagementOn')) is not None:
            return True
        return False

    def power_off(self):
        """Try to power off

        :param: None
        :return: bool - True if successful, False otherwise
        """
        out = self.__power_management('off').strip()
        if out.find(self.features.get('PowerManagementOff')) is not None:
            return True
        return False

    def power_reset(self):
        """Try to power reset

        :param: None
        :return: bool - True if successful, False otherwise
        """
        out = self.__power_management('reset').strip()
        if out.find(self.features.get('PowerManagementReset')) is not None:
            return True
        return False

    def power_reboot(self):
        """Try to power reboot

        :param: None
        :return: bool - True if successful, False otherwise
        """
        out = self.__power_management('cycle')
        if out.find(self.features.get('PowerManagementCycle')) is not None:
            return True
        return False

    def __chassis_management(self, command):
        """Try to do chassis management

            applicable: status, power, identify, policy,
                        restart_cause, poh, bootdev,
                        bootparam, selftest

        :param command: str - ipmitool command string acceptable for 'chassis'
        :return: object - output if successful, empty string otherwise
        """
        if command in self.features.get('ChassisManagement'):
            return self.__run_ipmi(['chassis', command])
        return ''

    def chassis_status(self):
        """Try to get chassis status

        :param: None
        :return: dict - dict if OK, {} otherwise
        """
        out = self.__chassis_management('status')
        return self.__convert2dict(out)

    def chassis_set_boot(self, device):
        """Set boot device

        :param device: str - boot device
        :return: bool - True if successful, False otherwise
        """
        out = ''
        if device in self.features.get('ChassisBootManagement'):
            out = self.__run_ipmi(['chassis', 'bootdev',
                                   device, 'options=persistent'])
        if out and out.find(self.features.get(
                'ChassisSetBootDevice')) is not None:
            return True
        return False

    def __lan_management(self, command):
        """Try to do lan management. applicable print, stats get/clear

        :param command: str - ipmitool command string acceptable for 'lan'
        :return: object - output if successful, empty string otherwise
        """
        if command in self.features.get('LanManagement'):
            return self.__run_ipmi(['lan', command])
        return ''

    def lan_status(self):
        """Try to get lan status

        :param: None
        :return: dict if OK, {} otherwise
        """
        out = self.__lan_management('print')
        return self.__convert2dict(out)

    def lan_stats(self):
        """Try to get lan stats info

        :param: None
        :return: dict if OK, {} otherwise
        """
        out = self.__lan_management('stats get')
        return self.__convert2dict(out)

    def lan_get_mac(self):
        """Try to get to get the system LAN1 and LAN2 MAC addresses

        :param: None
        :return: dict if OK, {} otherwise
        """
        out = self.raw_request('0x30 0x21')
        macs = out.split(" ")[4:]
        mac1 = ":".join(macs)
        mac2 = macs[:-1]
        mac2.append(hex(int(macs[-1], 16) + 1)[2:])
        mac2 = ":".join(mac2)
        if mac1 and mac2:
            return {'mac1': mac1, 'mac2': mac2}
        return {}

    def raw_request(self, raw_data):
        """Try to pass raw command to IPMI

        :param raw_data: str - raw ipmi command
        :return: output if successful, None otherwise
        """
        rawcmd = ['raw']
        rawcmd.extend(raw_data)
        return self.__run_ipmi(rawcmd)


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
        :param ipmi_previlegies: str - the user privileges level
                    values: (default OPERATOR) CALLBACK, USER, OPERATOR,
                             ADMINISTRATOR, OEM, NO ACCESS
        :param ipmi_host: str - remote host name
        :param ipmi_port: int - remote port number
        :param ipmi_lan_interface: str - the lan interface
                    values: (default 'lanplus'), lan, lanplus
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

        :param: None
        :return: bool - True if successful, False otherwise
        """
        self.uuid = uuid.uuid4()
        super(IpmiNode, self).define()

    def start(self):
        """Node start. Power on

        :param: None
        :return: bool - True if successful, False otherwise
        """
        # Boot device is not stored in bios, so it should
        # be set every time when node starts.
        self.conn.chassis_set_boot('pxe')

        if self.is_active():
            # Re-start active node
            res = self.reboot()
        else:
            res = self.conn.power_on()
        wait(self.is_active, timeout=60,
             timeout_msg="Node {0} / {1} wasn't started in 60 sec".
             format(self.name, self.ipmi_host))
        return res

    def create(self):
        """Node creating. Create env but don't power on after

        :param: None
        :return: bool - True if successful, False otherwise
        """
        self.save()

    def destroy(self):
        """Node destroy. Power off

        TODO: format hard drive

        :param: None
        :return: bool - True if successful, False otherwise
        """
        res = self.conn.power_off()
        wait(lambda: not self.is_active(), timeout=60,
             timeout_msg="Node {0} / {1} wasn't stopped in 60 sec".
             format(self.name, self.ipmi_host))
        return res

    def erase(self):
        """Node erase. Power off

        TODO: format hard drive

        :param: None
        :return: bool - True if successful, False otherwise
        """
        super(IpmiNode, self).delete()
        if self.is_active():
            return self.conn.power_off()
        return False

    def remove(self):
        """Node remove. Power off

        :param: None
        :return: bool - True if successful, False otherwise
        """
        return self.conn.power_off()

    def reset(self):
        """Node reset. Power reset

        :param: None
        :return: bool - True if successful, False otherwise
        """
        return self.conn.power_reset()

    def reboot(self):
        """Node reboot. Power reset

        :param: None
        :return: bool - True if successful, False otherwise
        """
        return self.conn.power_reset()

    def shutdown(self):
        """Shutdown Node

        Note: Actually we can do power off only
              but we have take into account
              safe shutdown if OS is already installed

        :param: None
        :return: bool - True if successful, False otherwise
        """
        return self.conn.power_off()
