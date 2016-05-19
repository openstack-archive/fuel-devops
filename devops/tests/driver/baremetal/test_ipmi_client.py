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


from django.test import TestCase
import mock

from devops.driver.baremetal.ipmi_client import IpmiClient


class IPMIClientTestCase(TestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        self.subprocess_mock = self.patch('devops.driver.baremetal.'
                                          'ipmi_client.subprocess')
        check_output = self.subprocess_mock.check_output
        check_output.return_value = 'ipmi_tool'
        self.popen_inst = self.subprocess_mock.Popen.return_value
        self.popen_inst.communicate.return_value = (1, 2)
        self.popen_inst.returncode = 0
        self.ipmi_user = 'admin'
        self.ipmi_password = 'password'
        self.ipmi_host = 'remote'
        self.ipmi_previlegies = 'OPERATOR'
        self.ipmi_lan_interface = 'lanplus'
        self.ipmi_port = 623
        self.name = 'NodeName'
        self.userlist = """ID Name Callin Link Auth IPMI Msg Channel Priv Limit
        101   admin            false   false      true       ADMINISTRATOR
        3   engineer         true    false      true       ADMINISTRATOR"""
        self.popen_inst.communicate.return_value = (self.userlist, 0)
        self.client = IpmiClient(self.ipmi_user, self.ipmi_password,
                                 self.ipmi_host,
                                 self.ipmi_previlegies,
                                 self.ipmi_lan_interface,
                                 self.ipmi_port, self.name)

    def tearDown(self):
        self.popen_inst.communicate.side_effect = (1, 2)

    def test_getuserid(self):
        self.popen_inst.communicate.return_value = (self.userlist, 0)
        assert int(self.client.userid) == 101

    def test_controller_info(self):
        retvalue = """Device ID                 : 32
                      Device Revision           : 1
                      Firmware Revision         : 2.15
                      IPMI Version              : 2.0
                      Manufacturer ID           : 10876
                      Manufacturer Name         : Supermicro
                      Product ID                : 2117 (0x0845)
                      Product Name              : Unknown (0x845)
                      Device Available          : yes
                      Provides Device SDRs      : no
                      Additional Device Support :
                        Sensor Device
                        SDR Repository Device
                        SEL Device
                        FRU Inventory Device
                        IPMB Event Receiver
                        IPMB Event Generator
                        Chassis Device"""
        self.popen_inst.communicate.return_value = (retvalue, 0)
        checkres = {'Additional Device Support': '',
                    'Device Available': 'yes',
                    'Device ID': '32',
                    'Device Revision': '1',
                    'Firmware Revision': '2.15',
                    'IPMI Version': '2.0',
                    'Manufacturer ID': '10876',
                    'Manufacturer Name': 'Supermicro',
                    'Product ID': '2117 (0x0845)',
                    'Product Name': 'Unknown (0x845)',
                    'Provides Device SDRs': 'no'}
        assert self.client.controller_info() == checkres

    def test_poweron(self):
        self.popen_inst.communicate.return_value = ('Chassis Power Control: '
                                                    'Up/On', 0)
        assert self.client.power_on()

    def test_poweroff(self):
        self.popen_inst.communicate.return_value = ('Chassis Power Control: '
                                                    'Down/Off', 0)
        assert self.client.power_off()

    def test_powerstatus(self):
        self.popen_inst.communicate.return_value = ('Chassis Power is on', 0)
        assert self.client.power_status() is not None

    def test_power_reset(self):
        self.popen_inst.communicate.return_value = ('Chassis Power Control: '
                                                    'Reset', 0)
        assert self.client.power_reset()

    def test_power_reboot(self):
        self.popen_inst.communicate.return_value = ('Chassis Power Control: '
                                                    'Cycle', 0)
        assert self.client.power_reboot()

    def test_chassis_status(self):
        retvalue = """System Power         : on
                      Power Overload       : false
                      Power Interlock      : inactive
                      Main Power Fault     : false
                      Power Control Fault  : false
                      Power Restore Policy : always-off
                      Last Power Event     :
                      Chassis Intrusion    : inactive
                      Front-Panel Lockout  : inactive
                      Drive Fault          : false
                      Cooling/Fan Fault    : false"""
        self.popen_inst.communicate.return_value = (retvalue, 0)
        checkres = {'Chassis Intrusion': 'inactive',
                    'Cooling/Fan Fault': 'false',
                    'Drive Fault': 'false',
                    'Front-Panel Lockout': 'inactive',
                    'Last Power Event': '',
                    'Main Power Fault': 'false',
                    'Power Control Fault': 'false',
                    'Power Interlock': 'inactive',
                    'Power Overload': 'false',
                    'Power Restore Policy': 'always-off',
                    'System Power': 'on'}
        assert self.client.chassis_status() == checkres

    def test_chassis_set_boot(self):
        retvalue = 'Set Boot Device to cdrom'
        self.popen_inst.communicate.return_value = (retvalue, 0)
        assert self.client.chassis_set_boot('cdrom')

    def test_lan_status(self):
        retvalue = """Set in Progress         : Set Complete
                      Auth Type Support       : NONE MD2 MD5 PASSWORD
                      Auth Type Enable        : Callback : MD2 MD5 PASSWORD
                                              : User     : MD2 MD5 PASSWORD
                                              : Operator : MD2 MD5 PASSWORD
                                              : Admin    : MD2 MD5 PASSWORD
                                              : OEM      : MD2 MD5 PASSWORD
                      IP Address Source       : Static Address
                      IP Address              : 5.43.225.36
                      Subnet Mask             : 255.255.255.0
                      MAC Address             : 0c:c4:7a:36:83:84
                      SNMP Community String   : public
                      IP Header               : TTL=0x00 Flags=0x00
                      BMC ARP Control         : ARP Responses Enabled
                      Get LAN Parameter 'Gratituous ARP' command failed: 0
                      Default Gateway IP      : 5.43.225.1
                      Default Gateway MAC     : 00:19:a9:89:b8:00
                      Backup Gateway IP       : 0.0.0.0
                      Backup Gateway MAC      : 00:00:00:00:00:00
                      802.1q VLAN ID          : Disabled
                      802.1q VLAN Priority    : 0
                      RMCP+ Cipher Suites     : 1,2,3,6,7,8,11,12
                      Cipher Suite Priv Max   : XaaaXXaaaXXaaXX
                                              :     X=Cipher Suite Unused
                                              :     c=CALLBACK
                                              :     u=USER
                                              :     o=OPERATOR
                                              :     a=ADMIN
                                              :     O=OEM"""
        self.popen_inst.communicate.return_value = (retvalue, 0)
        checkres = {'': 'O=OEM',
                   '802.1q VLAN ID': 'Disabled',
                   '802.1q VLAN Priority': '0',
                   'Auth Type Support': 'NONE MD2 MD5 PASSWORD',
                   'BMC ARP Control': 'ARP Responses Enabled',
                   'Backup Gateway IP': '0.0.0.0',
                   'Cipher Suite Priv Max': 'XaaaXXaaaXXaaXX',
                   'Default Gateway IP': '5.43.225.1',
                   "Get LAN Parameter 'Gratituous ARP' command failed": '0',
                   'IP Address': '5.43.225.36',
                   'IP Address Source': 'Static Address',
                   'IP Header': 'TTL=0x00 Flags=0x00',
                   'RMCP+ Cipher Suites': '1,2,3,6,7,8,11,12',
                   'SNMP Community String': 'public',
                   'Set in Progress': 'Set Complete',
                   'Subnet Mask': '255.255.255.0'}
        assert self.client.lan_status() == checkres

    def test_lan_stats(self):
        retvalue = """IP Rx Packet              : 65535
                      IP Rx Header Errors       : 0
                      IP Rx Address Errors      : 26890
                      IP Rx Fragmented          : 0
                      IP Tx Packet              : 65535
                      UDP Rx Packet             : 0
                      RMCP Rx Valid             : 34059
                      UDP Proxy Packet Received : 0
                      UDP Proxy Packet Dropped  : 0"""
        self.popen_inst.communicate.return_value = (retvalue, 0)
        checkres = {'IP Rx Address Errors': '26890',
                    'IP Rx Fragmented': '0',
                    'IP Rx Header Errors': '0',
                    'IP Rx Packet': '65535',
                    'IP Tx Packet': '65535',
                    'RMCP Rx Valid': '34059',
                    'UDP Proxy Packet Dropped': '0',
                    'UDP Proxy Packet Received': '0',
                    'UDP Rx Packet': '0'}
        assert self.client.lan_stats() == checkres

    def test_raw_request(self):
        retvalue = ' 45 08 00 01 0c c4 7a 33 26 7c'
        rawreq = '0x30 0x21'
        checkres = {'mac1': '01:0c:c4:7a:33:26:7c',
                    'mac2': '01:0c:c4:7a:33:26:7d'}
        self.popen_inst.communicate.return_value = (retvalue, 0)
        assert self.client.raw_request(rawreq) == retvalue
        assert self.client.lan_get_mac() == checkres
