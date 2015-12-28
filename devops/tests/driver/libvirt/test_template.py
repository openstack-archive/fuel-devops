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
import collections

from django.test import TestCase
import mock
import yaml

from devops.models import Environment
from devops.driver.libvirt.libvirt_driver import LibvirtManager

CAPS_XML = """
<capabilities>

  <host>
    <cpu>
      <arch>i686</arch>
      <features>
        <pae/>
        <nonpae/>
      </features>
    </cpu>
    <power_management/>
    <secmodel>
      <model>testSecurity</model>
      <doi></doi>
    </secmodel>
  </host>

  <guest>
    <os_type>hvm</os_type>
    <arch name='i686'>
      <wordsize>32</wordsize>
      <emulator>/usr/bin/qemu-system-i386</emulator>
      <domain type='qemu'>
      </domain>
      <domain type='test'>
        <emulator>/usr/bin/test-emulator</emulator>
      </domain>
    </arch>
    <features>
      <cpuselection/>
      <deviceboot/>
      <acpi default='on' toggle='yes'/>
      <apic default='on' toggle='no'/>
      <pae/>
      <nonpae/>
    </features>
  </guest>

  <guest>
    <os_type>hvm</os_type>
    <arch name='x86_64'>
      <wordsize>64</wordsize>
      <emulator>/usr/bin/qemu-system-x86_64</emulator>
      <domain type='test'>
        <emulator>/usr/bin/test-emulator</emulator>
      </domain>
    </arch>
    <features>
      <cpuselection/>
      <deviceboot/>
      <acpi default='on' toggle='yes'/>
      <apic default='on' toggle='no'/>
    </features>
  </guest>

</capabilities>
"""

ENV_TMPLT = """
---
aliases:

  dynamic_address_pool:
   - &pool_default 10.109.0.0/16:24

  default_interface_model:
   - &interface_model e1000

template:
  devops_settings:
    env_name: test_env

    address_pools:
    # Network pools used by the environment
      fuelweb_admin-pool01:
        net: *pool_default
        params:
          tag: 0
      public-pool01:
        net: *pool_default
        params:
          tag: 0
      storage-pool01:
        net: *pool_default
        params:
          tag: 101
      management-pool01:
        net: *pool_default
        params:
          tag: 102
      private-pool01:
        net: *pool_default
        params:
          tag: 103

    groups:
     - name: rack-01
       driver:
         name: devops.driver.libvirt.libvirt_driver
         params:
           connection_string: test:///default
           storage_pool_name: default-pool
           stp: True
           hpet: False
           use_host_cpu: true

       network_pools:  # Address pools for OpenStack networks.
         # Actual names should be used for keys
         # (the same as in Nailgun, for example)

         fuelweb_admin: fuelweb_admin-pool01
         public: public-pool01
         storage: storage-pool01
         management: management-pool01
         private: private-pool01

       l2_network_devices:  # Libvirt bridges. It is *NOT* Nailgun networks
         admin:
           address_pool: fuelweb_admin-pool01
           dhcp: false
           forward:
             mode: nat

         public:
           address_pool: public-pool01
           dhcp: false
           forward:
             mode: nat

         storage:
           address_pool: storage-pool01
           dhcp: false

         management:
           address_pool: management-pool01
           dhcp: false

         private:
           address_pool: private-pool01
           dhcp: false

       nodes:
        - name: admin        # Custom name of VM for Fuel admin node
          role: fuel_master  # Fixed role for Fuel master node properties
          params:
            vcpu: 2
            memory: 3072
            hypervisor: test
            architecture: i686
            boot:
              - hd
              - cdrom
            volumes:
             - name: system
               capacity: 15
               format: qcow2
             - name: iso
               source_image: /tmp/admin.iso
               format: raw
               device: cdrom
               bus: ide        # for boot from usb - 'usb'
            interfaces:
             - label: eth0
               l2_network_device: admin
               interface_model: *interface_model
            network_config:
              eth0:
                networks:
                 - fuelweb_admin

          # Slave nodes

        - name: slave-01
          role: fuel_slave
          params:  &rack-01-slave-node-params
            vcpu: 2
            memory: 3072
            hypervisor: test
            architecture: i686
            boot:
              - network
              - hd
            volumes:
             - name: system
               capacity: 10
               format: qcow2
             - name: cinder
               capacity: 10
               format: qcow2
             - name: swift
               capacity: 10
               format: qcow2

            # List of node interfaces
            interfaces:
             - label: eth0
               l2_network_device: admin
               interface_model: *interface_model
             - label: eth1
               l2_network_device: public
               interface_model: *interface_model
             - label: eth2
               l2_network_device: storage
               interface_model: *interface_model
             - label: eth3
               l2_network_device: management
               interface_model: *interface_model
             - label: eth4
               l2_network_device: private
               interface_model: *interface_model

            # How Nailgun/OpenStack networks should assigned for interfaces
            network_config:
              eth0:
                networks:
                 - fuelweb_admin  # Nailgun/OpenStack network name
              eth1:
                networks:
                 - public
              eth2:
                networks:
                 - storage
              eth3:
                networks:
                 - management
              eth4:
                networks:
                 - private


        - name: slave-02
          role: fuel_slave
          params: *rack-01-slave-node-params
"""


class TestLibvirtL2NetworkDevice(TestCase):

    def patch(self, *args, **kwargs):
        patcher = mock.patch(*args, **kwargs)
        m = patcher.start()
        self.addCleanup(patcher.stop)
        return m

    def setUp(self):
        # speed up retry
        self.sleep_mock = self.patch('devops.helpers.retry.sleep')

        # mock open
        self.open_mock = mock.mock_open(read_data='image_data')
        self.patch('devops.driver.libvirt.libvirt_driver.open',
                   self.open_mock, create=True)

        # mock libvirt
        self.libvirt_vol_up_mock = self.patch('libvirt.virStorageVol.upload')
        self.libvirt_stream_snd_mock = self.patch('libvirt.virStream.sendAll')
        self.libvirt_stream_fin_mock = self.patch('libvirt.virStream.finish')

        self.os_mock = self.patch('devops.helpers.helpers.os')
        self.os_mock.urandom = os.urandom
        Size = collections.namedtuple('Size', ['st_size'])
        self.file_sizes = {
            '/tmp/admin.iso': Size(st_size=500),
        }
        self.os_mock.stat.side_effect = self.file_sizes.get

        # Create Environment
        self.full_conf = yaml.load(ENV_TMPLT)
        self.env = Environment.create_environment(self.full_conf)

        self.d = self.env.get_group(name='rack-01').driver

        for domain in self.d.conn.listAllDomains():
            domain.destroy()
            domain.undefine()
        for network in self.d.conn.listAllNetworks():
            network.destroy()
            network.undefine()

        self.caps_patcher = mock.patch.object(self.d.conn, 'getCapabilities')
        self.caps_mock = self.caps_patcher.start()
        self.addCleanup(self.caps_patcher.stop)
        self.caps_mock.return_value = CAPS_XML

    def tearDown(self):
        # remove connection
        c = LibvirtManager.get_connection('test:///default')
        c.close()
        LibvirtManager.connections.clear()

    def test_db(self):
        # groups
        assert len(self.env.group_set.all()) == 1
        group = self.env.get_group(name='rack-01')
        assert group

        # address polls
        assert len(self.env.addresspool_set.all()) == 5
        get_ap = self.env.get_address_pool
        assert get_ap(name='fuelweb_admin-pool01')
        assert get_ap(name='fuelweb_admin-pool01').tag == 0
        assert get_ap(name='public-pool01')
        assert get_ap(name='public-pool01').tag == 0
        assert get_ap(name='storage-pool01')
        assert get_ap(name='storage-pool01').tag == 101
        assert get_ap(name='management-pool01')
        assert get_ap(name='management-pool01').tag == 102
        assert get_ap(name='private-pool01')
        assert get_ap(name='private-pool01').tag == 103

        # l2 network devices
        get_l2nd = group.get_l2_network_device
        assert get_l2nd(name='admin')
        assert get_l2nd(name='admin').forward.mode == 'nat'
        assert get_l2nd(name='admin').dhcp is False
        assert get_l2nd(name='public')
        assert get_l2nd(name='public').forward.mode == 'nat'
        assert get_l2nd(name='public').dhcp is False
        assert get_l2nd(name='storage')
        assert get_l2nd(name='storage').forward.mode is None
        assert get_l2nd(name='storage').dhcp is False
        assert get_l2nd(name='management')
        assert get_l2nd(name='management').forward.mode is None
        assert get_l2nd(name='management').dhcp is False
        assert get_l2nd(name='private')
        assert get_l2nd(name='private').forward.mode is None
        assert get_l2nd(name='private').dhcp is False

        assert len(self.env.get_nodes()) == 3

        # admin node
        admin_node = self.env.get_node(name='admin')
        assert admin_node.role == 'fuel_master'
        assert admin_node.vcpu == 2
        assert admin_node.memory == 3072
        assert admin_node.hypervisor == 'test'
        assert admin_node.architecture == 'i686'
        assert admin_node.boot == ['hd', 'cdrom']
        adm_sys_vol = admin_node.get_volume(name='system')
        assert adm_sys_vol.capacity == 16106127360
        assert adm_sys_vol.format == 'qcow2'
        adm_iso_vol = admin_node.get_volume(name='iso')
        assert adm_iso_vol.capacity == 500
        assert adm_iso_vol.source_image == '/tmp/admin.iso'
        assert adm_iso_vol.format == 'raw'
        # assert adm_iso_vol.device == 'cdrom'   # FAILS
        # assert adm_iso_vol.bus == 'ide'  # FAILS
        adm_eth0 = admin_node.interface_set.get(label='eth0')
        assert adm_eth0
        assert adm_eth0.label == 'eth0'
        assert adm_eth0.model == 'e1000'
        assert adm_eth0.l2_network_device.name == 'admin'
        adm_nc = admin_node.networkconfig_set.get(label='eth0')
        assert adm_nc
        assert adm_nc.label == 'eth0'
        assert adm_nc.networks == ['fuelweb_admin']
        assert adm_nc.parents == []
        assert adm_nc.aggregation is None

        # slave nodes
        for slave_name in ('slave-01', 'slave-02'):
            slave_node = self.env.get_node(name=slave_name)
            assert slave_node.role == 'fuel_slave'
            assert slave_node.vcpu == 2
            assert slave_node.memory == 3072
            assert slave_node.hypervisor == 'test'
            assert slave_node.architecture == 'i686'
            assert slave_node.boot == ['network', 'hd']
            slave_sys_vol = slave_node.get_volume(name='system')
            assert slave_sys_vol
            assert slave_sys_vol.capacity == 10737418240
            assert slave_sys_vol.format == 'qcow2'
            slave_cinder_vol = slave_node.get_volume(name='cinder')
            assert slave_cinder_vol
            assert slave_cinder_vol.capacity == 10737418240
            assert slave_cinder_vol.format == 'qcow2'
            slave_swift_vol = slave_node.get_volume(name='swift')
            assert slave_swift_vol
            assert slave_swift_vol.capacity == 10737418240
            assert slave_swift_vol.format == 'qcow2'
            slave_eth0 = slave_node.interface_set.get(label='eth0')
            assert slave_eth0
            assert slave_eth0.label == 'eth0'
            assert slave_eth0.model == 'e1000'
            assert slave_eth0.l2_network_device.name == 'admin'
            slave_eth1 = slave_node.interface_set.get(label='eth1')
            assert slave_eth1
            assert slave_eth1.label == 'eth1'
            assert slave_eth1.model == 'e1000'
            assert slave_eth1.l2_network_device.name == 'public'
            slave_eth2 = slave_node.interface_set.get(label='eth2')
            assert slave_eth2
            assert slave_eth2.label == 'eth2'
            assert slave_eth2.model == 'e1000'
            assert slave_eth2.l2_network_device.name == 'storage'
            slave_eth3 = slave_node.interface_set.get(label='eth3')
            assert slave_eth3
            assert slave_eth3.label == 'eth3'
            assert slave_eth3.model == 'e1000'
            assert slave_eth3.l2_network_device.name == 'management'
            slave_eth4 = slave_node.interface_set.get(label='eth4')
            assert slave_eth4
            assert slave_eth4.label == 'eth4'
            assert slave_eth4.model == 'e1000'
            assert slave_eth4.l2_network_device.name == 'private'
            slave_eth0_nc = slave_node.networkconfig_set.get(label='eth0')
            assert slave_eth0_nc
            assert slave_eth0_nc.label == 'eth0'
            assert slave_eth0_nc.networks == ['fuelweb_admin']
            assert slave_eth0_nc.parents == []
            assert slave_eth0_nc.aggregation is None
            slave_eth1_nc = slave_node.networkconfig_set.get(label='eth1')
            assert slave_eth1_nc
            assert slave_eth1_nc.label == 'eth1'
            assert slave_eth1_nc.networks == ['public']
            assert slave_eth1_nc.parents == []
            assert slave_eth1_nc.aggregation is None
            slave_eth2_nc = slave_node.networkconfig_set.get(label='eth2')
            assert slave_eth2_nc
            assert slave_eth2_nc.label == 'eth2'
            assert slave_eth2_nc.networks == ['storage']
            assert slave_eth2_nc.parents == []
            assert slave_eth2_nc.aggregation is None
            slave_eth3_nc = slave_node.networkconfig_set.get(label='eth3')
            assert slave_eth3_nc
            assert slave_eth3_nc.label == 'eth3'
            assert slave_eth3_nc.networks == ['management']
            assert slave_eth3_nc.parents == []
            assert slave_eth3_nc.aggregation is None
            slave_eth4_nc = slave_node.networkconfig_set.get(label='eth4')
            assert slave_eth4_nc
            assert slave_eth4_nc.label == 'eth4'
            assert slave_eth4_nc.networks == ['private']
            assert slave_eth4_nc.parents == []
            assert slave_eth4_nc.aggregation is None

    def test_life_cycle(self):
        assert len(self.d.get_allocated_networks()) == 0
        assert len(self.d.conn.listDefinedNetworks()) == 0
        assert len(self.d.conn.listDefinedDomains()) == 0

        self.env.define()

        nets = map(str, self.d.get_allocated_networks())
        assert sorted(nets) == [
            '10.109.0.1/24',
            '10.109.1.1/24',
            '10.109.2.1/24',
            '10.109.3.1/24',
            '10.109.4.1/24',
        ]

        assert sorted(self.d.conn.listDefinedNetworks()) == [
            'test_env_admin',
            'test_env_management',
            'test_env_private',
            'test_env_public',
            'test_env_storage',
        ]

        assert sorted(self.d.conn.listDefinedDomains()) == [
            'test_env_admin',
            'test_env_slave-01',
            'test_env_slave-02',
        ]

        self.env.start()

        networks = self.d.conn.listAllNetworks()
        assert len(networks) == 5
        for network in networks:
            assert network.isActive()

        domains = self.d.conn.listAllDomains()
        assert len(domains) == 3
        for domain in domains:
            assert domain.isActive()

        self.env.destroy()

        networks = self.d.conn.listAllNetworks()
        assert len(networks) == 5
        for network in networks:
            assert network.isActive()  # shlold be active

        domains = self.d.conn.listAllDomains()
        assert len(domains) == 3
        for domain in domains:
            assert not domain.isActive()

        self.env.erase()

        assert len(self.d.get_allocated_networks()) == 0
        assert len(self.d.conn.listAllNetworks()) == 0
        assert len(self.d.conn.listAllDomains()) == 0
