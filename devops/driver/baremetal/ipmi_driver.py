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

from devops.error import DevopsError
from devops import logger
from devops.models.base import ParamField


def run_ipmi(user, password, remote_host, cmd,
             level='OPERATOR', remote_lan_interface='lanplus',
             remote_port=None, nodename=None):
    """Run command through ipmitool

    :param user: str - the user login for IPMI board
    :param password: str - the user password
    :param remote_host: str - remote host name
    :param cmd: list - impi command
    :param level: str - the user privileges level. (default OPERATOR)
           values: CALLBACK, USER, OPERATOR, ADMINISTRATOR, OEM, NO ACCESS
    :param remote_lan_interface: str - the lan interface
           values: (default 'lanplus'), lan, lanplus
    :param remote_port: int - remote port number
    :param nodename: str - node name
    :return: object - data if successful, None otherwise
    """

    try:
        ipmitool_cmd = subprocess.check_output(["which", "ipmitool"]).strip()
        if not ipmitool_cmd:
            raise DevopsError('ipmitool not found')
    except Exception:
        raise DevopsError('Node:{} ipmi_host:{} ipmitool has not installed.\
                           No chance to go over'.format(nodename,
                                                        remote_host))
    impi_cmd_dict = {'ipmitool': ipmitool_cmd,
                     'remote_lan_interface': remote_lan_interface,
                     'remote_host': remote_host, 'remote_port': remote_port,
                     'user': user, 'password': password, 'level': level,
                     'cmd': cmd}
    lerrors = [(key, value) for (key, value) in impi_cmd_dict.items()
               if value is None]
    if lerrors:
        raise DevopsError('Node:{} ipmi_host:{} ipmitool arguments.\
                           key={}, value={} are not valid'.format(nodename,
                                                                  remote_host,
                                                                  lerrors[0],
                                                                  lerrors[1]))

    ipmi_cmd = [ipmitool_cmd,
                '-I', remote_lan_interface,
                '-H', remote_host,
                '-U', user, '-P', password,
                '-L', level]
    if remote_port:
        ipmi_cmd.extend(['-p', remote_port])
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
                          'has failed with the exception: {}'
                          .format(nodename, remote_host, cmd, message))

    if (out is None) or code != 0:
        logger.debug("rcode ={} or err ={}".format(code, err))
        raise DevopsError('Node:{} Remote:{} ipmitool command [{}] '
                          'has failed with the message: {}'
                          .format(nodename, remote_host, cmd, err))
    return out


def convert2dict(data):
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


class Driver(IpmiDriver):
    """Driver params from template. keep in DB"""
    pass


class L2NetworkDevice(IpmiL2NetworkDevice):
    """L2NetworkDevice params from template. keep in DB"""
    pass


class Volume(IpmiVolume):
    """Volume params from template"""
    pass


class Node(IpmiNode):
    """IPMI Node

            Intel IPMI specification:
            http://www.intel.ru/content/dam/www/public/us/en/documents/
            product-briefs/ipmi-second-gen-interface-spec-v2-rev1-1.pdf

            The Node shall provide ability to manage remote
            baremetal node through impi interface by using
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
        :param ipmi_cmd: str - impi command
    """

    uuid = ParamField()  # LEGACY, for compatibility reason
    boot = ParamField(default='pxe')
    ipmi_user = ParamField()
    ipmi_password = ParamField()
    ipmi_previlegies = ParamField(default='OPERATOR')
    ipmi_host = ParamField()
    ipmi_lan_interface = ParamField(default="lanplus")
    ipmi_port = ParamField(default=623)
    impi_cmd = ParamField(default="ipmitool ")
    features = {
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

    def get_capabilities(self):
        """Get capabilities

        :param: None
        :return: dict - supporting features and commands
        """
        return self.features

    def exists(self):
        """Check if node exists

        :param: None
        :return: bool - True if successful, False otherwise
        """
        return self.check_remote_host(self.ipmi_user, self.ipmi_password,
                                      self.ipmi_host)

    def is_active(self):
        """Check if node is active

        Note: we have to check power on and
              we have take into account that OS is working on remote host
        TODO: let's double check remote OS despite power is on

        :param: None
        :return: bool - True if successful, False otherwise.
        """
        return (0 == self.power_status(self.ipmi_user, self.ipmi_password,
                                       self.ipmi_host))

    def define(self):
        """Prepare node to start

        TODO: Mount ISO
        TODO: Set boot device
        Note: need to set boot device at first. Create record in DB

        :param: None
        :return: bool - True if successful, False otherwise
        """
        self.uuid = uuid.uuid4()
        super(Node, self).define()

    def start(self):
        """Node start. Power on

        :param: None
        :return: bool - True if successful, False otherwise
        """
        # Boot device is not stored in bios, so it should
        # be set every time when node starts.
        self.chassis_set_boot(self.ipmi_user, self.ipmi_password,
                              self.ipmi_host, self.boot)

        if self.is_active():
            # Re-start active node
            return self.reboot()
        else:
            return self.power_on(self.ipmi_user, self.ipmi_password,
                                 self.ipmi_host)

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
        return self.power_off(self.ipmi_user, self.ipmi_password,
                              self.ipmi_host)

    def erase(self):
        """Node erase. Power off

        TODO: format hard drive

        :param: None
        :return: bool - True if successful, False otherwise
        """
        super(Node, self).delete()
        if self.is_active():
            return self.power_off(self.ipmi_user, self.ipmi_password,
                                  self.ipmi_host)
        return False

    def remove(self):
        """Node remove. Power off

        :param: None
        :return: bool - True if successful, False otherwise
        """
        return self.power_off(self.ipmi_user, self.ipmi_password,
                              self.ipmi_host)

    def reset(self):
        """Node reset. Power reset

        :param: None
        :return: bool - True if successful, False otherwise
        """
        return self.power_reset(self.ipmi_user, self.ipmi_password,
                                self.ipmi_host)

    def reboot(self):
        """Node reboot. Power reset

        :param: None
        :return: bool - True if successful, False otherwise
        """
        return self.power_reset(self.ipmi_user, self.ipmi_password,
                                self.ipmi_host)

    def shutdown(self):
        """Shutdown Node

        Note: Actually we can do power off only
              but we have take into account
              safe shutdown if OS is already installed

        :param: None
        :return: bool - True if successful, False otherwise
        """
        return self.power_off(self.ipmi_user, self.ipmi_password,
                              self.ipmi_host)

    def controller_management(self, user, passw, host, command):
        """Try to do user controller

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :param command: str - ipmitool command string acceptable for 'power'
        :return: object - output if successful, empty string otherwise
        """
        if command in self.get_capabilities().get('ControllerManagement'):
            return run_ipmi(user, passw, host, ['mc', command],
                            nodename=self.name)
        return ''

    def controller_info(self, user, passw, host):
        """Try to controller status

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :return: dict - dict object if successful, {} otherwise
        """
        out = self.controller_management(user, passw, host, 'info')
        return convert2dict(out)

    def check_remote_host(self, user, passw, host):
        """Check baremetal node through ipmi

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :return: bool - True if successful, False otherwise
        """
        return self.controller_info(user, passw, host) != {}

    def user_management(self, user, passw, host, command):
        """Try to do user management

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :param command: str - ipmitool command string acceptable for 'power'
        :return: object - output if successful, empty string otherwise
        """
        if command in self.get_capabilities().get('UserManagement'):
            return run_ipmi(user, passw, host, ['user', command],
                            nodename=self.name)
        return ''

    def user_list(self, user, passw, host):
        """Try to user list

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :return: list - list object if successful, [] otherwise
        """
        res = []
        out = self.user_management(user, passw, host, 'list')
        if out.find(self.get_capabilities().get(
                'UserManagementListReply')) is not None:
            # let's get user ID and Privileges. UserID is a first column
            userlist = out.strip().split('\n')
            for i in userlist[1:]:
                tstr = i.split(' ')
                idn, priv, name = tstr[0], tstr[-1], " ".join(
                    [value for value in tstr[1:4] if value])
                res.append({'id': idn, 'name': name, 'priv': priv})
        return res

    def get_user_id(self, user, passw, host):
        """Get user id

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :return: id if successful, None otherwise.
        """
        userlist = self.user_list(user, passw, host)
        for i in userlist:
            if user == i.get('name'):
                return i.get('id')
        return None

    def power_management(self, user, passw, host, command):
        """Try to do power management. status/on/off/reset

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :param command: str - ipmitool command string acceptable for 'power'
        :return: object - output if successful, empty string otherwise
        """
        if command in self.get_capabilities().get('PowerManagement'):
            return run_ipmi(user, passw, host, ['power', command],
                            nodename=self.name)
        return ''

    def power_status(self, user, passw, host):
        """Try to get power status

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :return: 1 - power on, 0 - power off, None otherwise.
        """
        out = self.power_management(user, passw, host, 'status').strip()
        if out.find(self.get_capabilities().get(
                'PowerManagementStatus', [])[0]):
            return 1
        elif out.find(self.get_capabilities().get(
                'PowerManagementStatus', [])[1]):
            return 0
        return None

    def power_on(self, user, passw, host):
        """Try to power on

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :return: bool - True if successful, False otherwise
        """
        out = self.power_management(user, passw, host, 'on').strip()
        if out.find(self.get_capabilities().get(
                'PowerManagementOn')) is not None:
            return True
        return False

    def power_off(self, user, passw, host):
        """Try to power off

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :return: bool - True if successful, False otherwise
        """
        out = self.power_management(user, passw, host, 'off').strip()
        if out.find(self.get_capabilities().get(
                'PowerManagementOff')) is not None:
            return True
        return False

    def power_reset(self, user, passw, host):
        """Try to power reset

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :return: bool - True if successful, False otherwise
        """
        out = self.power_management(user, passw, host, 'reset').strip()
        if out.find(self.get_capabilities().get(
                'PowerManagementReset')) is not None:
            return True
        return False

    def power_reboot(self, user, passw, host):
        """Try to power reboot

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :return: bool - True if successful, False otherwise
        """
        out = self.power_management(user, passw, host, 'cycle')
        if out.find(self.get_capabilities().get(
                'PowerManagementCycle')) is not None:
            return True
        return False

    def chassis_management(self, user, passw, host, command):
        """Try to do chassis management

            applicable: status, power, identify, policy,
                        restart_cause, poh, bootdev,
                        bootparam, selftest

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :param command: str - ipmitool command string acceptable for 'chassis'
        :return: object - output if successful, empty string otherwise
        """
        if command in self.get_capabilities().get('ChassisManagement'):
            return run_ipmi(user, passw, host, ['chassis', command],
                            nodename=self.name)
        return ''

    def chassis_status(self, user, passw, host):
        """Try to get chassis status

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :return: dict - dict if OK, {} otherwise
        """
        out = self.chassis_management(user, passw, host, 'status')
        return convert2dict(out)

    def chassis_set_boot(self, user, passw, host, device):
        """Set boot device

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :param device: str - boot device
        :return: bool - True if successful, False otherwise
        """
        out = ''
        if device in self.get_capabilities().get('ChassisBootManagement'):
            out = run_ipmi(user, passw, host, ['chassis', 'bootdev', device,
                                               'options=persistent'],
                           nodename=self.name)
        if out and out.find(self.get_capabilities().get(
                'ChassisSetBootDevice')) is not None:
            return True
        return False

    def lan_management(self, user, passw, host, command):
        """Try to do lan management. applicable print, stats get/clear

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :param command: str - ipmitool command string acceptable for 'lan'
        :return: object - output if successful, empty string otherwise
        """
        if command in self.get_capabilities().get('LanManagement'):
            return run_ipmi(user, passw, host, ['lan', command],
                            nodename=self.name)
        return ''

    def lan_status(self, user, passw, host):
        """Try to get lan status

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :return: dict if OK, {} otherwise
        """
        out = self.lan_management(user, passw, host, 'print')
        return convert2dict(out)

    def lan_stats(self, user, passw, host):
        """Try to get lan stats info

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :return: dict if OK, {} otherwise
        """
        out = self.lan_management(user, passw, host, 'stats get')
        return convert2dict(out)

    def lan_get_mac(self, user, passw, host):
        """Try to get to get the system LAN1 and LAN2 MAC addresses

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :return: dict if OK, {} otherwise
        """
        out = self.raw_request(user, passw, host, '0x30 0x21')
        macs = out.split(" ")[4:]
        mac1 = ":".join(macs)
        mac2 = macs[:-1]
        mac2.append(hex(int(macs[-1], 16)+1)[2:])
        mac2 = ":".join(mac2)
        if mac1 and mac2:
            return {'mac1': mac1, 'mac2': mac2}
        return {}

    def raw_request(self, user, passw, host, raw_data):
        """Try to pass raw command to IPMI

        :param user: str - the user login for IPMI board
        :param password: str - the user password
        :param host: str - remote host name
        :param raw_data: str - raw ipmi command
        :return: output if successful, None otherwise
        """
        rawcmd = ['raw']
        rawcmd.extend(raw_data)
        return run_ipmi(user, passw, host, rawcmd, nodename=self.name)
