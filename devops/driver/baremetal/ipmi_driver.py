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
import subprocess
import uuid

from devops import DevopsError
from devops.helpers.retry import retry
from devops import logger
from devops.models.base import ParamField
from devops.models.driver import Driver as DriverBase
from devops.models.network import L2NetworkDevice as L2NetworkDeviceBase
from devops.models.node import Node as NodeBase
from devops.models.volume import Volume as VolumeBase


def run_ipmi(user, password, remote_host, cmd,
             level='OPERATOR',
             remote_lan_interface='lanplus',
             remote_port=None, sol=False):
    """Run command through ipmitool

    Args: args(str) -- ipmitool command string
    Returns: data if successful, None otherwise.
    """

    def _check_system_ready():
        """Double check that ipmitool is presented

        Args: None
        Returns:
            True if successful, False otherwise.
        """
        return (0 == subprocess.call(["which", "ipmitool"]))

    if not (_check_system_ready()):
        hostname = subprocess.check_output("hostname")
        raise DevopsError('Host:{} Remote:{} ipmitool has not installed.\
                           No change to go over'.format(hostname, 
                                                        remote_host))

    ipmi_cmd = ['ipmitool',
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
    except Exception as e:
        logger.debug('{}'.format(e))
        return None

    if (out is None) or code != 0:
        logger.debug("rcode ={} or err ={}".format(code, err))
        hostname = subprocess.check_output("hostname")
        raise DevopsError('Host:{} Remote:{} ipmitool command [{}]\
                           has failed'.format(hostname, remote_host, cmd))

    if sol:
        return out, pipe
    return out


class Driver(DriverBase):
    # params from template. keep is in DB
    pass


class L2NetworkDevice(L2NetworkDeviceBase):
    pass


class Volume(VolumeBase):
    pass


class Node(NodeBase):
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

        Args:
`           user(str)
            password(str)
            previlegies(Optional(str))
            remote_host(str)
            remote_port(Optional(int))
            remote_lan_interface(Optional(str))

        Attributes:
            ipmi_user(str)          -- the user login for IPMI board. mandatory
            ipmi_password(str)      -- the user password. mandatory.
            ipmi_previlegies(str)   -- the user privileges level. (default 3)
                    values: 1 - CALLBACK, 2 - USER, 3 - OPERATOR
                            4 - ADMINISTRATOR, 5 - OEM, 15 - NO ACCESS
            ipmi_host(str)          -- remote host name. mandatory
            ipmi_port(int)          -- remote port number.
            ipmi_lan_interface(str) -- the lan interface. (default 'lanplus')
                    values: lan, lanplus
    """

    uuid = ParamField()
    ipmi_user = ParamField()
    ipmi_password = ParamField()
    ipmi_previlegies = ParamField(default='OPERATOR')
    ipmi_host = ParamField()
    ipmi_lan_interface = ParamField(default="lanplus")
    ipmi_port = ParamField(default=623)
    impi_cmd = ParamField(default="ipmitool ")

    @staticmethod
    def get_capabilities():
        """Get capabilities

        Note: self.capabilities shall be set if it is None
        Args: None
        Returns: capabilities dictionary.
        """
        features = {'PowerManagement': ['status', 'on', 'off',
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
        return features

    @retry()
    def exists(self):
        """Check if node exists

        Args: None
        Returns: True if successful, False otherwise.
        """
        return Node.check_remote_host(self.ipmi_user, self.ipmi_password,
                                      self.ipmi_host)

    @retry()
    def is_active(self):
        """Check if node is active

        Note: we have to check power on and
              we have take into account that OS is working on remote host
        TODO: let's double check remote OS despite power is on
        Args: None
        Returns: True if successful, False otherwise.
        """
        return (Node.power_status(self.ipmi_user, self.ipmi_password,
                                  self.ipmi_host) > 0)

    def send_keys(self,  keys):
        """Send keys to node

        Note: SOL (Serial over lan) shall be used.

            sol activate help us to do serial over lan communication
            sol is active and we can see output and pass keys to remote host
            amd somehow to manage remote host. It is true until remote OS
            will be started and SOL will not be worked until some
            manipulations inside of remote OS. Please take a look at IPMI
            specification at first.

        Args:
            keys(list)

        Attributes:
            keys(list)  -- list of keys which shall be sent.
        For example Ctrl+S (enter to BIOS) - escape seq shall be sent
        """
        pass

    @retry()
    def define(self):
        """Prepare node to start

        - Mount ISO (TODO)
        - Set boot device (TODO)

        Note:   need to set boot device at first
                create record in DB
        Args: None
        Returns: True if successful, False otherwise.
        """
        # name = _underscored(
        #     deepgetattr(self, 'group.environment.name'),
        #     self.name,
        # )
        # local_disk_devices = []
        # local_interfaces = []
        self.uuid = uuid.uuid4()
        super(Node, self).define()

    def start(self):
        """Node start

        Note: power on; boot start
        Args: None
        Returns: True if successful, False otherwise.
        """
        return Node.power_on(self.ipmi_user, self.ipmi_password,
                             self.ipmi_host)

    def create(self, verbose=False):
        """Node creating

        Note: create env but don't power on after
        Args: None
        Returns: True if successful, False otherwise.
        """
        self.save()

    def destroy(self):
        """Node destroy

        Note: power off
        TODO: format hard drive
        Args: None
        Returns: True if successful, False otherwise.
        """
        return Node.power_off(self.ipmi_user, self.ipmi_password,
                              self.ipmi_host)

    def erase(self):
        """Node erase

        Note: power off
        TODO: format hard drive
        Args: None
        Returns: True if successful, False otherwise.
        """
        super(Node, self).delete()
        if self.is_active():
            return Node.power_off(self.ipmi_user, self.ipmi_password,
                                  self.ipmi_host)
        return False

    @retry()
    def remove(self, verbose=False):
        """Node remove

        Note: power off
        Args: None
        Returns: True if successful, False otherwise.
        """
        return Node.power_off(self.ipmi_user, self.ipmi_password,
                              self.ipmi_host)

    @retry()
    def reset(self):
        """Node reset

        Note: power reset
        Args: None
        Returns: True if successful, False otherwise.
        """
        return Node.power_reset(self.ipmi_user, self.ipmi_password,
                                self.ipmi_host)

    @retry()
    def reboot(self):
        """Node reboot

        Note: power reset
        Args: None
        Returns: True if successful, False otherwise.
        """
        return Node.power_reset(self.ipmi_user, self.ipmi_password,
                                self.ipmi_host)

    @retry()
    def shutdown(self, node):
        """Shutdown Node

        Note: Actually we can do power off only
              but we have take into account
              safe shutdown if OS is already installed
        Args: None
        Returns: True if successful, False otherwise.
        """
        return Node.power_off(self.ipmi_user, self.ipmi_password,
                              self.ipmi_host)

    # -------------------------  STATIC METHODS ------------------------------
    @staticmethod
    def controller_management(user, passw, host, command):
        """Try to do user controller

        applicable: list

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
            command(str)    -- ipmitool command string acceptable for 'power'
        Returns: output if successful, empty string otherwise.
        """
        if command in Node.get_capabilities().get('ControllerManagement'):
            return run_ipmi(user, passw, host, ['mc', command])
        return ''

    @staticmethod
    def controller_info(user, passw, host):
        """Try to controller status

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
        Returns: dict if successful, {} otherwise.
        """
        out = Node.controller_management(user, passw, host, 'info')
        return Node._convert2dict2(out)

    @staticmethod
    def check_remote_host(user, passw, host):
        """Check baremetal node through ipmi

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
        Returns: True if successful, False otherwise.
        """
        return Node.controller_info(user, passw, host) != {}

    @staticmethod
    def user_management(user, passw, host, command):
        """Try to do user management

        applicable: list

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
            command(str) -- ipmitool command string acceptable for 'power'
        Returns: output if successful, empty string otherwise.
        """
        if command in Node.get_capabilities().get('UserManagement'):
            return run_ipmi(user, passw, host, ['user', command])
        return ''

    @staticmethod
    def user_list(user, passw, host):
        """Try to user list

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
        Returns: list if successful, [] otherwise.
        """
        res = []
        out = Node.user_management(user, passw, host, 'list')
        if out.find(Node.get_capabilities().get(
                'UserManagementListReply')) is not None:
            # let's get user ID and Privileges. UserID is a first column
            userlist = out.strip().split('\n')
            for i in userlist[1:]:
                ss = i.split(' ')
                id, priv, name = ss[0], ss[-1], " ".join(
                    [value for value in ss[1:4] if value])
                res.append({'id': id, 'name': name, 'priv': priv})
        return res

    @staticmethod
    def get_user_id(user, passw, host):
        """Get user id

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
        Returns: id if successful, None otherwise.
        """
        userlist = Node.user_list(user, passw, host)
        for i in userlist:
            if user == i.get('name'):
                return i.get('id')
        return None

    @staticmethod
    def power_management(user, passw, host, command):
        """Try to do power management

        applicable: status/on/off/reset

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
            command(str) -- ipmitool command string acceptable for 'power'
        Returns: output if successful, empty string otherwise.
        """
        if command in Node.get_capabilities().get('PowerManagement'):
            return run_ipmi(user, passw, host, ['power', command])
        return ''

    @staticmethod
    def power_status(user, passw, host):
        """Try to get power status

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
        Returns: 1 - power on, 0 - power off, None otherwise.
        """
        out = Node.power_management(user, passw, host, 'status').strip()
        if out.find(Node.get_capabilities().get(
                'PowerManagementStatus', [])[0]):
            return 1
        elif out.find(Node.get_capabilities().get(
                'PowerManagementStatus', [])[1]):
            return 0
        return None

    @staticmethod
    def power_on(user, passw, host):
        """Try to power on

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
        Returns: True if successful, False otherwise.
        """
        out = Node.power_management(user, passw, host, 'on').strip()
        if out.find(Node.get_capabilities().get(
                'PowerManagementOn')) is not None:
            return True
        return False

    @staticmethod
    def power_off(user, passw, host):
        """Try to power off

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
        Returns: True if successful, False otherwise.
        """
        out = Node.power_management(user, passw, host, 'off').strip()
        if out.find(Node.get_capabilities().get(
                'PowerManagementOff')) is not None:
            return True
        return False

    @staticmethod
    def power_reset(user, passw, host):
        """Try to power reset

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
        Returns: True if successful, False otherwise.
        """
        out = Node.power_management(user, passw, host, 'reset').strip()
        if out.find(Node.get_capabilities().get(
                'PowerManagementReset')) is not None:
            return True
        return False

    @staticmethod
    def power_reboot(user, passw, host):
        """Try to power reboot

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
        Returns: True if successful, False otherwise.
        """
        out = Node.power_management(user, passw, host, 'cycle')
        if out.find(Node.get_capabilities().get(
                'PowerManagementCycle')) is not None:
            return True
        return False

    @staticmethod
    def chassis_management(user, passw, host, command):
        """Try to do chassis management

            applicable: status, power, identify, policy,
                        restart_cause, poh, bootdev,
                        bootparam, selftest

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
            command(str) -- ipmitool command string acceptable for 'chassis'
        Returns: output if successful, empty string otherwise.
        """
        if command in Node.get_capabilities().get('ChassisManagement'):
            return run_ipmi(user, passw, host, ['chassis', command])
        return ''

    @staticmethod
    def chassis_status(user, passw, host):
        """Try to get chassis status

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
        Returns: dict if OK, empty dict - {} otherwise.
        """
        out = Node.chassis_management(user, passw, host, 'status')
        return Node._convert2dict(out)

    @staticmethod
    def chassis_set_boot(user, passw, host, device):
        """Set boot device

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
            device(str)     -- boot device. mandatory
        Returns: True if successful, False otherwise.
        """
        out = ''
        if device in Node.get_capabilities().get('ChassisBootManagement'):
            out = run_ipmi(user, passw, host, ['chassis', 'bootdev', device])
            print (out)
        if out and out.find(Node.get_capabilities().get(
                'ChassisSetBootDevice')) is not None:
            return True
        return False

    @staticmethod
    def lan_management(user, passw, host, command):
        """Try to do lan management

        applicable: print
                    stats get
                    stats clear
        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
            command(str) -- ipmitool command string acceptable for 'lan'
        Returns: output if successful, empty string otherwise.
        """
        if command in Node.get_capabilities().get('LanManagement'):
            return run_ipmi(user, passw, host, ['lan', command])
        return ''

    @staticmethod
    def lan_status(user, passw, host):
        """Try to get lan status

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
        Returns: dict if OK, empty dict - {} otherwise.
        """
        out = Node.lan_management(user, passw, host, 'print')
        return Node._convert2dict2(out)

    @staticmethod
    def lan_stats(user, passw, host):
        """Try to get lan stats info

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
        Returns: dict if OK, empty dict - {} otherwise.
        """
        out = Node.lan_management(user, passw, host, 'stats get')
        return Node._convert2dict(out)

    @staticmethod
    def lan_get_mac(user, passw, host):
        """Try to get to get the system LAN1 and LAN2 MAC addresses

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
        Returns: dict if OK, empty dict - {} otherwise.
        """
        out = Node.raw_request(user, passw, host, '0x30 0x21')
        macs = out.split(" ")[4:]
        mac1 = ":".join(macs)
        mac2 = macs[:-1]
        mac2.append(hex(int(macs[-1], 16)+1)[2:])
        mac2 = ":".join(mac2)
        if mac1 and mac2:
            return {'mac1': mac1, 'mac2': mac2}
        return {}

    @staticmethod
    def raw_request(user, passw, host, raw_data):
        """Try to pass raw command to IPMI

        Args:
            user(str)       -- the user login for IPMI board. mandatory.
            password(str)   -- the user password. mandatory.
            host(str)       -- remote host name. mandatory
            raw_data(str)   -- raw ipmi command
        Returns: output if successful, None otherwise.
        """
        rawcmd = ['raw']
        rawcmd.extend(raw_data)
        return run_ipmi(user, passw, host, rawcmd)

    @staticmethod
    def _convert2dict(data):
        """Convert data output to dict

        Args:
            data(str)   -- ipmi command output
        Returns: dict if OK, {} otherwise.
        """
        res = {}
        if data:
            for i in data.split('\n'):
                if i:
                    key, value = map(str.strip, i.split(':'))
                    res.update({key: value})
        return res

    @staticmethod
    def _convert2dict2(data):
        """Convert data output to dict

        Note: sometime ipmi command output is more complicated then key: value
              but we still would like to have key: value dict
        Args:
            data(str)   -- ipmi command output
        Returns: dict if OK, {} otherwise.
        """
        res = {}
        keepkey = None
        if data:
            for i in data.split('\n'):
                if i:
                    index = i.find(':')
                    if index > 0:
                        key = i[:index].strip()
                        value = i[index+1:].strip()
                        # index2 = value.find(':')
                    else:
                        value = i.strip()
                        key = keepkey
                        index = 0

                    if key and index > 0:
                        res.update({key: value})
                        keepkey = key
                    else:
                        newvalue = res.get(keepkey, [])
                        if not isinstance(newvalue, list):
                            newvalue = []
                        newvalue.append(value)
                        res.update({keepkey: newvalue})
        return res
