#    Copyright 2013 - 2016 Mirantis, Inc.
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

import datetime
import itertools
import os
import re
import shutil
import time
import uuid
import warnings
# noinspection PyPep8Naming
import xml.etree.ElementTree as ET

from django.conf import settings
from django.utils import functional
import libvirt
import netaddr
import paramiko

from devops.driver.libvirt import libvirt_xml_builder as builder
from devops import error
from devops.helpers import cloud_image_settings
from devops.helpers import decorators
from devops.helpers import helpers
from devops.helpers import scancodes
from devops.helpers import ssh_client
from devops.helpers import subprocess_runner
from devops import logger
from devops.models import base
from devops.models import driver
from devops.models import network
from devops.models import node
from devops.models import volume


class _LibvirtManager(object):

    def __init__(self):
        libvirt.virInitialize()
        libvirt.registerErrorHandler(_LibvirtManager._error_handler, self)
        self.connections = {}

    def get_connection(self, connection_string):
        """Get libvirt connection for connection string

        :type connection_string: str
        """
        if connection_string in self.connections:
            conn = self.connections[connection_string]
            if conn.isAlive():
                # Use a cached connection only if it is alive
                return conn
            else:
                logger.error("Connection to libvirt '{0}' is broken, create a"
                             " new connection".format(connection_string))
        # Create a new connection
        conn = libvirt.open(connection_string)
        self.connections[connection_string] = conn
        return conn

    def _error_handler(self, error):
        # this handler redirects libvirt messages to debug logger
        if len(error) > 2 and error[2] is not None:
            logger.debug(error[2])
        else:
            logger.debug(error)


LibvirtManager = _LibvirtManager()


class Snapshot(object):

    def __init__(self, snapshot):
        self._snapshot = snapshot

    @property
    def __snapshot_files(self):
        """Return snapshot files

        :rtype: list
        """
        snap_files = []
        snap_memory = self._xml_tree.findall('./memory')[0]
        if snap_memory.get('file') is not None:
            snap_files.append(snap_memory.get('file'))
        return snap_files

    def delete_snapshot_files(self):
        """Delete snapshot external files"""
        snap_type = self.get_type
        if snap_type == 'external':
            for snap_file in self.__snapshot_files:
                if os.path.isfile(snap_file):
                    try:
                        os.remove(snap_file)
                        logger.info(
                            "Delete external snapshot file {0}".format(
                                snap_file))
                    except Exception:
                        logger.info(
                            "Cannot delete external snapshot file {0}"
                            " must be deleted from cron script".format(
                                snap_file))

    @property
    @decorators.retry(libvirt.libvirtError)
    def xml(self):
        """Snapshot XML representation

        :rtype: str
        """
        xml = self._snapshot.getXMLDesc(0)
        snapshot_xmltree = ET.fromstring(xml)

        # Get cpu model from domain definition as it is not available
        # in snapshot XML for host-passthrough cpu mode
        cpu = snapshot_xmltree.findall('./domain/cpu')
        if cpu and 'mode' in cpu[0].attrib:
            cpu_mode = cpu[0].get('mode')
            if cpu_mode == 'host-passthrough':
                domain = self._snapshot.getDomain()
                domain_xml = domain.XMLDesc(
                    libvirt.VIR_DOMAIN_XML_UPDATE_CPU)
                domain_xmltree = ET.fromstring(domain_xml)
                cpu_element = domain_xmltree.find('./cpu')
                domain_element = snapshot_xmltree.findall('./domain')[0]
                domain_element.remove(domain_element.findall('./cpu')[0])
                domain_element.append(cpu_element)

        return helpers.xml_tostring(snapshot_xmltree)

    @property
    def _xml_tree(self):
        return ET.fromstring(self.xml)

    @property
    @decorators.retry(libvirt.libvirtError)
    def children_num(self):
        return self._snapshot.numChildren()

    @property
    def created(self):
        timestamp = self._xml_tree.findall('./creationTime')[0].text
        return datetime.datetime.utcfromtimestamp(float(timestamp))

    @property
    def disks(self):
        disks = {}
        xml_snapshot_disks = self._xml_tree.find('./disks')
        for xml_disk in xml_snapshot_disks:
            if xml_disk.get('snapshot') == 'external':
                disks[xml_disk.get('name')] = xml_disk.find(
                    'source').get('file')
        return disks

    @property
    def get_type(self):
        """Return snapshot type"""
        snap_memory = self._xml_tree.findall('./memory')[0]
        if snap_memory.get('snapshot') == 'external':
            return 'external'
        for disk in self._xml_tree.iter('disk'):
            if disk.get('snapshot') == 'external':
                return 'external'
        return 'internal'

    @property
    def memory_file(self):
        return self._xml_tree.findall('./memory')[0].get('file')

    @property
    def name(self):
        return self._snapshot.getName()

    @property
    def parent(self):
        return self._snapshot.getParent()

    @property
    def state(self):
        return self._xml_tree.findall('state')[0].text

    def delete(self, flags):
        return self._snapshot.delete(flags)

    def __repr__(self):
        return "<{0} {1}/{2}>".format(self.__class__.__name__,
                                      self.name, self.created)


class LibvirtDriver(driver.Driver):
    """libvirt driver

    :param use_host_cpu: When creating nodes, should libvirt's
        CPU "host-model" mode be used to set CPU settings. If set to False,
        default mode ("custom") will be used.  (default: True)

    Note: This class is imported as Driver at .__init__.py
    """

    connection_string = base.ParamField(default="qemu:///system")
    storage_pool_name = base.ParamField(default="default")
    stp = base.ParamField(default=True)
    hpet = base.ParamField(default=True)
    use_host_cpu = base.ParamField(default=True)
    enable_acpi = base.ParamField(default=False)
    enable_nwfilters = base.ParamField(default=False)
    reboot_timeout = base.ParamField()
    use_hugepages = base.ParamField(default=False)
    vnc_password = base.ParamField()

    _device_name_generators = {}

    @property
    def conn(self):
        """Connection to libvirt api"""
        # noinspection PyTypeChecker
        return LibvirtManager.get_connection(self.connection_string)

    def get_capabilities(self):
        """Get host capabilities

        This method is deprecated. Use `capabilities` property instead.

        :rtype : ET
        """
        return self.capabilities

    @functional.cached_property
    def capabilities(self):
        return ET.fromstring(self.conn.getCapabilities())

    def node_list(self):
        # virConnect.listDefinedDomains() only returns stopped domains
        #   https://bugzilla.redhat.com/show_bug.cgi?id=839259
        return [item.name() for item in self.conn.listAllDomains()]

    @decorators.retry(libvirt.libvirtError)
    def get_allocated_networks(self):
        """Get list of allocated networks

        :rtype : List
        """
        allocated_networks = []
        for nwk in self.conn.listAllNetworks():
            et = ET.fromstring(nwk.XMLDesc())
            ip = et.find('ip[@address]')
            if ip is not None:
                address = ip.get('address')
                prefix_or_netmask = ip.get('prefix') or ip.get('netmask')
                allocated_networks.append(netaddr.IPNetwork(
                    "{0:>s}/{1:>s}".format(address, prefix_or_netmask)))
        return allocated_networks

    @decorators.retry(libvirt.libvirtError)
    def get_allocated_device_names(self):
        """Get list of existing bridge names and network devices

        :rtype : List
        """
        names = []

        # Local Network Devices
        for dev in self.conn.listAllDevices():
            xml = ET.fromstring(dev.XMLDesc())
            name_el = xml.find('./capability/interface')
            if name_el is None:
                continue
            name = name_el.text
            names.append(name)

        # Network Bridges
        for net in self.conn.listAllNetworks():
            names.append(net.bridgeName())

        return names

    def get_available_device_name(self, prefix):
        """Get available name for network device or bridge

        :type prefix: str
        :rtype : String
        """
        allocated_names = self.get_allocated_device_names()
        if prefix not in self._device_name_generators:
            self._device_name_generators[prefix] = (
                '{}{}'.format(prefix, i) for i in itertools.count())
        all_names = self._device_name_generators[prefix]

        for name in all_names:
            if name in allocated_names:
                continue
            return name

    @decorators.retry(libvirt.libvirtError)
    def get_libvirt_version(self):
        return self.conn.getLibVersion()

    @property
    def shell(self):
        """Return an instance of the shell command runner

        - If self.connection_string contains '+ssh://', then will be used
          SSHClient with parameters taken from self.connection_string:
          username, host and port, for example:
          connection_string: qemu+ssh://<username>@<host>:<port>/system
        - Else, a subprocess_runner.Subprocess() will be returned
        """
        if '+ssh://' in self.connection_string:
            # Using SSHClient to execute shell commands on remote host
            # Regexp to extract username from the libvirt URI.
            # See http://libvirt.org/remote.html#Remote_URI_reference
            results = re.search("""
                \+ssh:\/\/                   # prefix: '+ssh://'
                (?:(?P<user>[\w\-\.\/]+)@)?  # group 1 [optional]: username
                (?P<host>[\w\-\.\/]+)        # group 2: hostname
                (?::(?P<port>\d{1,5}))?      # group 3 [optional]: port
                /.+                          # suffix
                """, self.connection_string, re.VERBOSE)
            username = results.group('user') or os.getlogin()
            host = results.group('host')
            port = int(results.group('port') or 22)

            agent = paramiko.Agent()
            keys = agent.get_keys()
            if not keys:
                # SSH Agent doesn't contain keys, trying to get key from file
                key_file = '~/.ssh/id_rsa'
                # TODO(ddmitriev): SSH keys should be used as a default
                # fallback in the SSHClient for cases when no password or keys
                # were specified. This try/except code with hardcoded key_file
                # should be removed after implementation of this fallback.
                try:
                    key = paramiko.RSAKey.from_private_key_file(
                        os.path.expanduser(key_file))
                except (paramiko.SSHException, IOError):
                    raise error.DevopsError(
                        "Unable to read RSA key from '{}'".format(key_file))
                logger.debug("Initializing SSHClient for username:'{0}', host:"
                             "'{1}', port:'{2}'".format(username, host, port))
                keys = [key]
            return ssh_client.SSHClient(
                host=host,
                port=port,
                auth=ssh_client.SSHAuth(
                    username=username,
                    keys=keys))
        else:
            # Using SubprocessClient to execute shell commands on local host
            logger.debug("Initializing subprocess_runner for local host")
            return subprocess_runner.Subprocess


class LibvirtL2NetworkDevice(network.L2NetworkDevice):
    """L2 network device based on libvirt Network

       forward:
         mode: nat   #  One of : None, 'nat', 'route', 'bridge', 'private',
                     #           'vepa', 'passthrough', 'hostdev'
       dhcp: false   #  Enable DHCP for this network device.
                     #  To use 'dhcp', make sure that the address_pool used
                     #  for this network device has an 'ip_range' with name
                     #  'dhcp'.
       stp: true    #  Enable stp for this network device. If not specified,
                     #  than will be used 'stp' setting from the driver object.

       has_pxe_server: false  #  Enable PXE server for this device
       tftp_root_dir: /tmp    #  Specity root directory for TFTP server

       vlan_ifaces: []  #  List of integer values that will be used to create
                        #  tagged interfaces to the network device.
       parent_iface:    #  Interface that will be added to the current libvirt
                        #  network device (to the linux bridge)
         phys_dev: eth1  # Physical interface name.
                         # If forward.mode == 'bridge', then 'phys_dev' should
                         # contain an already existing bridge name that will be
                         # used for libvirt network.
         #  or
         l2_net_dev: public  # Name of the fuel-devops network device
         tag: 200            # and the tag that was created with 'vlan_ifaces'
                             # for some other l2_network_device ('public' here,
                             # that use linux bridge virbrNN),
                             # to include virbrNN@200 to the current network
                             # device (linux bridge).

       Template example for NATed networks
       -----------------------------------
       # Nodes should have at least two interfaces connected to the following
       # L2 networks:
       # admin: for admin/PXE network
       # openstack_br: for all other tagged networks.

       l2_network_devices:  # Libvirt bridges. It is *NOT* Nailgun networks

         # Admin/PXE network
         # Virtual nodes can be connected here (Fuel master, OpenStack nodes).
         # A physical interface ${BAREMETAL_ADMIN_IFACE} will be added
         # to the libvirt network with name 'admin' to allow connectivity
         # between VMs, baremetal servers and system tests on this server.
         admin:
           address_pool: fuelweb_admin-pool01
           dhcp: false
           stp: true
           forward:
             mode: nat
           parent_iface:
             phys_dev: !os_env BAREMETAL_ADMIN_IFACE

         # Libvirt bridge dedicated for access to a baremetal network
         # ${BAREMETAL_OS_NETS_IFACE} with tagged OpenStack networks.
         # This is intermediate bridge, where tagged interfaces with tags
         # 100, 101 and 102 will be created, to get untagged access
         # to the tagged networks.
         # IT IS *NOT* FOR ADDING ADDRESS POOLS!
         # ONLY FOR CONNECTING VM's INTERFACES!
         openstack_br:
           stp: false
           vlan_ifaces:
            - 100
            - 101
            - 102
            - 103
           parent_iface:
             phys_dev: !os_env BAREMETAL_OS_NETS_IFACE

         # Public libvirt bridge, only for keeping IP address.
         # 'nat' forward can be omitted if the baremetal network has
         # it's own gateway.
         # This l2 libvirt network can be omitted if no access required
         # from system tests to the nodes via public addresses.
         # IT IS *NOT* FOR CONNECTING VM's INTERFACES!
         # ONLY FOR ACCESS TO THE PUBLIC NETWORK ADDRESSES
         # AND 'NAT' FROM PUBLIC TO WAN.
         public:
           address_pool: public-pool01
           dhcp: false
           forward:
             mode: nat
           parent_iface:
             l2_net_dev: openstack_br
             tag: 100

         # Storage libvirt bridge, only for keeping IP address.
         # This l2 libvirt network can be omitted if no access required
         # from system tests to the nodes via storage addresses.
         # IT IS *NOT* FOR CONNECTING VM's INTERFACES!
         # ONLY FOR ACCESS TO THE STORAGE NETWORK ADDRESSES
         storage:
           address_pool: storage-pool01
           dhcp: false
           parent_iface:
             l2_net_dev: openstack_br
             tag: 101

         # Management libvirt bridge, only for keeping IP address.
         # This l2 libvirt network can be omitted if no access required
         # from system tests to the nodes via management addresses.
         # IT IS *NOT* FOR CONNECTING VM's INTERFACES!
         # ONLY FOR ACCESS TO THE MANAGEMENT NETWORK ADDRESSES
         management:
           address_pool: management-pool01
           dhcp: false
           parent_iface:
             l2_net_dev: openstack_br
             tag: 102

         # Private libvirt bridge, only for keeping IP address.
         # This l2 libvirt network can be omitted if no access required
         # from system tests to the nodes via private addresses.
         # IT IS *NOT* FOR CONNECTING VM's INTERFACES!
         # ONLY FOR ACCESS TO THE PRIVATE NETWORK ADDRESSES
         private:
           address_pool: private-pool01
           dhcp: false
           parent_iface:
             l2_net_dev: openstack_br
             tag: 103

       Template example for existing bridges
       -------------------------------------

       l2_network_devices:  # Libvirt bridges. It is *NOT* Nailgun networks
         admin:
           forward:
             mode: bridge
           parent_iface:
             phys_dev: !os_env BAREMETAL_ADMIN_IFACE

         public:
           forward:
             mode: bridge
           parent_iface:
             phys_dev: !os_env BAREMETAL_PUBLIC_IFACE

         private:
           forward:
             mode: bridge
           parent_iface:
             phys_dev: !os_env BAREMETAL_PRIVATE_IFACE


    Note: This class is imported as L2NetworkDevice at .__init__.py
    """
    uuid = base.ParamField()

    forward = base.ParamMultiField(
        mode=base.ParamField(
            choices=(None, 'nat', 'route', 'bridge', 'private',
                     'vepa', 'passthrough', 'hostdev'),
        )
    )
    dhcp = base.ParamField(default=False)
    stp = base.ParamField()

    has_pxe_server = base.ParamField(default=False)
    tftp_root_dir = base.ParamField()

    vlan_ifaces = base.ParamField(default=[])
    parent_iface = base.ParamMultiField(
        phys_dev=base.ParamField(default=None),
        l2_net_dev=base.ParamField(default=None),
        tag=base.ParamField(default=None),
    )

    def __repr__(self):
        return (
            '{0}(name={1}, address_pool={2!r}, group={3}, uuid={4!r}, '
            'forward={5!r}, dhcp={6!r}, stp={7!r}, vlan_ifaces={8!r}, '
            'parent_iface={9!s}@{10})'.format(
                self.__class__.__name__,
                self.name,
                self.address_pool.net,
                self.group.name,
                self.uuid,
                self.forward.mode,
                self.dhcp,
                self.stp,
                self.vlan_ifaces,
                self.parent_iface.phys_dev or self.parent_iface.l2_net_dev,
                self.parent_iface.tag
            ))

    @property
    @decorators.retry(libvirt.libvirtError)
    def _libvirt_network(self):
        try:
            return self.driver.conn.networkLookupByUUIDString(self.uuid)
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_NETWORK:
                logger.error("Network not found by UUID: {}".format(self.uuid))
                return None
            else:
                raise

    @decorators.retry(libvirt.libvirtError)
    def bridge_name(self):
        return self._libvirt_network.bridgeName()

    @property
    def network_name(self):
        """Get network name

        :rtype : String
        """
        return helpers.underscored(
            helpers.deepgetattr(self, 'group.environment.name'),
            self.name)

    @decorators.retry(libvirt.libvirtError)
    def is_active(self):
        """Check if network is active

        :rtype : Boolean
        """
        return self._libvirt_network.isActive()

    @decorators.retry(libvirt.libvirtError, delay=3)
    def define(self):
        # define filter first
        if self.driver.enable_nwfilters:
            filter_xml = builder.LibvirtXMLBuilder.build_network_filter(
                name=self.network_name)
            self.driver.conn.nwfilterDefineXML(filter_xml)

        if self.forward.mode == 'bridge':
            bridge_name = self.parent_iface.phys_dev
        else:
            bridge_name = self.driver.get_available_device_name(prefix='virbr')

        # TODO(ddmitriev): check if 'vlan' package installed
        # Define tagged interfaces on the bridge
        for vlanid in self.vlan_ifaces:
            self.iface_define(name=bridge_name, vlanid=vlanid)

        # Define libvirt network
        ip_network_address = None
        ip_network_prefixlen = None
        dhcp_range_start = None
        dhcp_range_end = None
        addresses = []
        if self.address_pool is not None:
            # Reserved names 'l2_network_device' and 'dhcp'
            ip_network_address = self.address_pool.get_ip('l2_network_device')

            # Workaround for fuel-qa compatibility, if 'l2_network_device'
            # address was not reserved in the YAML template
            if not ip_network_address:
                ip_network_address = str(self.address_pool.ip_network[1])

            ip_network_prefixlen = str(self.address_pool.ip_network.prefixlen)
            dhcp_range_start = self.address_pool.ip_range_start('dhcp')
            dhcp_range_end = self.address_pool.ip_range_end('dhcp')

            for interface in self.interfaces:
                for address in interface.addresses:
                    ip_addr = netaddr.IPAddress(address.ip_address)
                    if ip_addr in self.address_pool.ip_network:
                        addresses.append(dict(
                            mac=str(interface.mac_address),
                            ip=str(address.ip_address),
                            name=interface.node.name
                        ))

        xml = builder.LibvirtXMLBuilder.build_network_xml(
            network_name=self.network_name,
            bridge_name=bridge_name,
            addresses=addresses,
            forward=self.forward.mode,
            ip_network_address=ip_network_address,
            ip_network_prefixlen=ip_network_prefixlen,
            dhcp_range_start=dhcp_range_start,
            dhcp_range_end=dhcp_range_end,
            stp=self.stp if (self.stp is not None) else self.driver.stp,
            has_pxe_server=self.has_pxe_server,
            dhcp=self.dhcp,
            tftp_root_dir=self.tftp_root_dir,
        )
        ret = self.driver.conn.networkDefineXML(xml)
        ret.setAutostart(True)
        self.uuid = ret.UUIDString()

        super(LibvirtL2NetworkDevice, self).define()

    def start(self):
        self.create()

    @decorators.retry(libvirt.libvirtError)
    def create(self, *args, **kwargs):
        if not self.is_active():
            self._libvirt_network.create()

        # Insert a specified interface into the network's bridge
        parent_name = ''
        if (self.parent_iface.phys_dev is not None and
                self.forward.mode != 'bridge'):
            # TODO(ddmitriev): check that phys_dev is not the device
            # that is used for default route
            parent_name = self.parent_iface.phys_dev

        elif self.parent_iface.l2_net_dev is not None:
            l2_net_dev = self.group.environment.get_env_l2_network_device(
                name=self.parent_iface.l2_net_dev)
            parent_name = l2_net_dev.bridge_name()

        # Add specified interface to the current bridge
        if parent_name is not '':
            if self.parent_iface.tag:
                parent_iface_name = "{0}.{1}".format(
                    parent_name, str(self.parent_iface.tag))
            else:
                parent_iface_name = parent_name

            # TODO(ddmitriev): check if the parent_name link is UP
            # before adding it to the bridge
            cmd = 'sudo brctl addif {br} {iface}'.format(
                br=self.bridge_name(), iface=parent_iface_name)

            # TODO(ddmitriev): check that the parent_name is not included
            # to any bridge before adding it to the current bridge instead
            # of this try/except workaround
            try:
                self.driver.shell.check_call(cmd)
            except error.DevopsCalledProcessError:
                pass

    @decorators.retry(libvirt.libvirtError)
    def destroy(self):
        self._libvirt_network.destroy()

    @decorators.retry(libvirt.libvirtError)
    def remove(self, *args, **kwargs):
        if self.uuid:
            if self.exists():
                # Stop network
                if self.is_active():
                    self._libvirt_network.destroy()
                # Remove tagged interfaces
                for vlanid in self.vlan_ifaces:
                    iface_name = "{}.{}".format(self.bridge_name(),
                                                str(vlanid))
                    self.iface_undefine(iface_name=iface_name)
                # Remove network
                if self._libvirt_network:
                    self._libvirt_network.undefine()
                # Remove nwfiler
                if self.driver.enable_nwfilters:
                    if self._nwfilter:
                        self._nwfilter.undefine()
        super(LibvirtL2NetworkDevice, self).remove()

    @decorators.retry(libvirt.libvirtError)
    def exists(self):
        """Check if network exists

        :type network_uuid: str
            :rtype : Boolean
        """
        try:
            self.driver.conn.networkLookupByUUIDString(self.uuid)
            return True
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_NETWORK:
                return False
            else:
                raise

    @decorators.retry(libvirt.libvirtError)
    def iface_define(self, name, ip=None, prefix=None, vlanid=None):
        """Define bridge interface

        :type name: String
        :type ip: IPAddress
        :type prefix: Integer
        :type vlanid: Integer
            :rtype : None
        """
        self.driver.conn.interfaceDefineXML(
            builder.LibvirtXMLBuilder.build_iface_xml(
                name, ip, prefix, vlanid))

    @decorators.retry(libvirt.libvirtError)
    def iface_undefine(self, iface_name):
        """Start interface

        :type iface_name: String
            :rtype : None
        """
        try:
            iface = self.driver.conn.interfaceLookupByName(iface_name)
        except libvirt.libvirtError:
            return None
        iface.undefine()

    @property
    @decorators.retry(libvirt.libvirtError)
    def _nwfilter(self):
        """Returns NWFilter object"""
        try:
            return self.driver.conn.nwfilterLookupByName(self.network_name)
        except libvirt.libvirtError:
            logger.error("NWFilter not found by name: {}".format(
                self.network_name))
            return None

    @property
    def is_blocked(self):
        """Returns state of network"""
        if not self.driver.enable_nwfilters:
            return False
        if not self._nwfilter:
            return False

        filter_xml = ET.fromstring(self._nwfilter.XMLDesc())
        return filter_xml.find('./rule') is not None

    @decorators.retry(libvirt.libvirtError)
    def block(self):
        """Block all traffic in network"""
        if not self.driver.enable_nwfilters:
            return
        if not self._nwfilter:
            raise error.DevopsError(
                'Unable to block network {0}: nwfilter not found!'
                ''.format(self.network_name))

        filter_xml = builder.LibvirtXMLBuilder.build_network_filter(
            name=self.network_name,
            uuid=self._nwfilter.UUIDString(),
            rule=dict(action='drop',
                      direction='inout',
                      priority='-1000'))
        self.driver.conn.nwfilterDefineXML(filter_xml)

    @decorators.retry(libvirt.libvirtError)
    def unblock(self):
        """Unblock all traffic in network"""
        if not self.driver.enable_nwfilters:
            return
        if not self._nwfilter:
            raise error.DevopsError(
                'Unable to unblock network {0}: nwfilter not found!'
                ''.format(self.network_name))

        filter_xml = builder.LibvirtXMLBuilder.build_network_filter(
            name=self.network_name,
            uuid=self._nwfilter.UUIDString())
        self.driver.conn.nwfilterDefineXML(filter_xml)


class LibvirtVolume(volume.Volume):
    """Note: This class is imported as Volume at .__init__.py """

    uuid = base.ParamField()
    capacity = base.ParamField(default=None)  # in gigabytes
    format = base.ParamField(default='qcow2', choices=('qcow2', 'raw'))
    source_image = base.ParamField(default=None)
    serial = base.ParamField()
    wwn = base.ParamField()
    multipath_count = base.ParamField(default=0)
    cloudinit_meta_data = base.ParamField(default=None)
    cloudinit_user_data = base.ParamField(default=None)

    @property
    @decorators.retry(libvirt.libvirtError)
    def _libvirt_volume(self):
        try:
            return self.driver.conn.storageVolLookupByKey(self.uuid)
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_STORAGE_VOL:
                logger.error("Volume not found by UUID: {}".format(self.uuid))
                return None
            else:
                raise

    @decorators.retry(libvirt.libvirtError)
    def define(self):
        # Generate libvirt volume name
        if self.node:
            name = helpers.underscored(
                helpers.deepgetattr(self, 'node.group.environment.name'),
                helpers.deepgetattr(self, 'node.name'),
                self.name,
            )
        elif self.group:
            name = helpers.underscored(
                helpers.deepgetattr(self, 'group.environment.name'),
                helpers.deepgetattr(self, 'group.name'),
                self.name,
            )
        else:
            raise error.DevopsError(
                "Can't craete volume that is not "
                "associated with any node or group")

        # Find backing store format and path
        backing_store_path = None
        backing_store_format = None
        if self.backing_store:
            if not self.backing_store.exists():
                raise error.DevopsError(
                    "Can't create volume {!r}. backing_store volume {!r} does "
                    "not exists.".format(self.name, self.backing_store.name))
            backing_store_path = self.backing_store.get_path()
            backing_store_format = self.backing_store.format

        # Select capacity
        if self.capacity:
            # if capacity specified, use it first
            capacity = int(self.capacity * 1024 ** 3)
        elif self.source_image is not None:
            # limit capacity to the sorse image file size
            capacity = helpers.get_file_size(self.source_image)
        elif self.backing_store:
            # limit capacity to backing_store capacity
            capacity = self.backing_store.get_capacity()
        else:
            raise error.DevopsError(
                "Can't create volume {!r}: no capacity or "
                "source_image specified".format(self.name))

        # Generate xml
        pool_name = self.driver.storage_pool_name
        pool = self.driver.conn.storagePoolLookupByName(pool_name)
        xml = builder.LibvirtXMLBuilder.build_volume_xml(
            name=name,
            capacity=capacity,
            vol_format=self.format,
            backing_store_path=backing_store_path,
            backing_store_format=backing_store_format,
        )

        # Define volume
        libvirt_volume = pool.createXML(xml, 0)

        # Save uuid
        self.uuid = libvirt_volume.key()

        # Set serial and wwn
        if not self.serial:
            self.serial = uuid.uuid4().hex
        if not self.wwn:
            self.wwn = '0' + ''.join(uuid.uuid4().hex)[:15]

        super(LibvirtVolume, self).define()

        # Upload predefined image to the volume
        if self.source_image is not None:
            self.upload(self.source_image, capacity)

    @decorators.retry(libvirt.libvirtError)
    def remove(self, *args, **kwargs):
        if self.uuid:
            if self.exists():
                self._libvirt_volume.delete(0)
        super(LibvirtVolume, self).remove()

    @decorators.retry(libvirt.libvirtError)
    def get_capacity(self):
        """Get volume capacity in bytes"""
        return self._libvirt_volume.info()[1]

    @decorators.retry(libvirt.libvirtError)
    def get_format(self):
        xml_desc = ET.fromstring(self._libvirt_volume.XMLDesc(0))
        return xml_desc.find('target/format[@type]').get('type')

    @decorators.retry(libvirt.libvirtError)
    def get_path(self):
        return self._libvirt_volume.path()

    @staticmethod
    def fill_from_exist():
        msg = 'LibvirtVolume.fill_from_exist() is deprecated and do nothing'
        warnings.warn(msg, DeprecationWarning)
        logger.debug(msg)

    @decorators.retry(libvirt.libvirtError, count=2)
    def upload(self, path, capacity=0):
        def chunk_render(_, _size, _fd):
            return _fd.read(_size)

        size = helpers.get_file_size(path)
        current_size = self._libvirt_volume.info()[1]

        # resize volume if more space required to upload the image
        if size > current_size:
            # NOTE: qcow2 doesn't support shrinking images yet
            self._libvirt_volume.resize(size)
            self.save()

        with open(path, 'rb') as fd:
            stream = self.driver.conn.newStream(0)
            self._libvirt_volume.upload(
                stream=stream, offset=0,
                length=size, flags=0)
            stream.sendAll(chunk_render, fd)
            stream.finish()

        if capacity > size:
            # Resize the uploaded image to specified capacity
            try:
                self._libvirt_volume.resize(capacity)
                self.save()
            except libvirt.libvirtError:
                err = libvirt.virGetLastError()
                if (err[0] == libvirt.VIR_ERR_INVALID_ARG and
                        err[1] == libvirt.VIR_FROM_STORAGE):
                    logger.error(
                        "Cannot resize volume {0}: {1}"
                        .format(self._libvirt_volume.path(), err[2]))
                else:
                    raise

    @decorators.retry(libvirt.libvirtError)
    def get_allocation(self):
        """Get allocated volume size

        :rtype : int
        """
        return self._libvirt_volume.info()[2]

    @decorators.retry(libvirt.libvirtError)
    def exists(self):
        """Check if volume exists"""
        try:
            self.driver.conn.storageVolLookupByKey(self.uuid)
            return True
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_STORAGE_VOL:
                return False
            else:
                raise

    # Changed behaviour. It is not a @classmethod anymore; thus
    # 'backing_store' variable deprecated, child of the current snapshot
    # will be created.
    def create_child(self, name):
        """Create new volume based on current volume

        :rtype : Volume
        """
        cls = self.driver.get_model_class('Volume')
        return cls.objects.create(
            name=name,
            node=self.node,
            format=self.format,
            backing_store=self,
        )

    # LEGACY, for fuel-qa compatibility
    @classmethod
    def volume_get_predefined(cls, uuid):
        """Get predefined volume

        :rtype : Volume
        """
        msg = ('LibvirtVolume.volume_get_predefined() is deprecated. '
               'Please use Volumes associated with Groups')
        warnings.warn(msg, DeprecationWarning)
        logger.debug(msg)

        try:
            volume = cls.objects.get(uuid=uuid)
        except cls.DoesNotExist:
            volume = cls(uuid=uuid)
        if not volume.exists():
            raise error.DevopsError(
                'Predefined volume {!r} not found'.format(uuid))
        volume.format = volume.get_format()
        volume.save()
        return volume


class LibvirtNode(node.Node):
    """Note: This class is imported as Node at .__init__.py """

    uuid = base.ParamField()
    hypervisor = base.ParamField(default='kvm', choices=('kvm', 'test'))
    os_type = base.ParamField(default='hvm', choices=['hvm'])
    architecture = base.ParamField(
        default='x86_64', choices=['x86_64', 'i686'])
    boot = base.ParamField(default=['network', 'cdrom', 'hd'])
    vcpu = base.ParamField(default=1)
    memory = base.ParamField(default=1024)
    has_vnc = base.ParamField(default=True)
    bootmenu_timeout = base.ParamField(default=0)
    numa = base.ParamField(default=[])
    cloud_init_volume_name = base.ParamField()
    cloud_init_iface_up = base.ParamField()

    @property
    @decorators.retry(libvirt.libvirtError)
    def _libvirt_node(self):
        try:
            return self.driver.conn.lookupByUUIDString(self.uuid)
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_DOMAIN:
                logger.error("Domain not found by UUID: {}".format(self.uuid))
                return None
            else:
                raise

    def get_vnc_port(self):
        """Get VNC port

            :rtype : String
        """
        xml_desc = ET.fromstring(
            self._libvirt_node.XMLDesc(0))
        vnc_element = xml_desc.find('devices/graphics[@type="vnc"][@port]')
        if vnc_element is not None:
            return vnc_element.get('port')

    @property
    def vnc_password(self):
        return self.driver.vnc_password

    @decorators.retry(libvirt.libvirtError)
    def exists(self):
        """Check if node exists

            :rtype : Boolean
        """
        try:
            self.driver.conn.lookupByUUIDString(self.uuid)
            return True
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_DOMAIN:
                return False
            else:
                raise

    @decorators.retry(libvirt.libvirtError)
    def is_active(self):
        """Check if node is active

            :rtype : Boolean
        """
        return bool(self._libvirt_node.isActive())

    def send_keys(self, keys):
        """Send keys to node

        :type keys: String
            :rtype : None
        """
        key_codes = scancodes.from_string(str(keys))
        for key_code in key_codes:
            if isinstance(key_code[0], str):
                if key_code[0] == 'wait':
                    time.sleep(1)
                continue
            self._libvirt_node.sendKey(0, 0, list(key_code), len(key_code), 0)

    @decorators.retry(libvirt.libvirtError)
    def define(self):
        """Define node

            :rtype : None
        """
        name = helpers.underscored(
            helpers.deepgetattr(self, 'group.environment.name'),
            self.name,
        )

        local_disk_devices = []
        for disk in self.disk_devices:
            local_disk_devices.append(dict(
                disk_type=disk.type,
                disk_device=disk.device,
                disk_volume_format=disk.volume.format,
                disk_volume_path=disk.volume.get_path(),
                disk_bus=disk.bus,
                disk_target_dev=disk.target_dev,
                disk_serial=disk.volume.serial,
                disk_wwn=disk.volume.wwn if disk.multipath_enabled else None,
            ))

        local_interfaces = []
        for interface in self.interfaces:
            if interface.type != 'network':
                raise NotImplementedError(
                    message='Interface types different from network are not '
                            'implemented yet')

            l2_dev = interface.l2_network_device
            if self.driver.enable_nwfilters:
                filter_name = helpers.underscored(
                    helpers.deepgetattr(self, 'group.environment.name'),
                    l2_dev.name,
                    interface.mac_address
                )
            else:
                filter_name = None  # do not refer to interface filter
            local_interfaces.append(dict(
                interface_type=interface.type,
                interface_mac_address=interface.mac_address,
                interface_network_name=l2_dev.network_name,
                # target_get will be generated by libvirt with prefix 'vnet'
                interface_target_dev=None,
                interface_model=interface.model,
                interface_filter=filter_name,
            ))

        emulator = self.driver.get_capabilities().find(
            'guest/arch[@name="{0:>s}"]/'
            'domain[@type="{1:>s}"]/emulator'.format(
                self.architecture, self.hypervisor)).text
        node_xml = builder.LibvirtXMLBuilder.build_node_xml(
            name=name,
            hypervisor=self.hypervisor,
            use_host_cpu=self.driver.use_host_cpu,
            vcpu=self.vcpu,
            memory=self.memory,
            use_hugepages=self.driver.use_hugepages,
            hpet=self.driver.hpet,
            os_type=self.os_type,
            architecture=self.architecture,
            boot=self.boot,
            reboot_timeout=self.driver.reboot_timeout,
            bootmenu_timeout=self.bootmenu_timeout,
            emulator=emulator,
            has_vnc=self.has_vnc,
            vnc_password=self.driver.vnc_password,
            local_disk_devices=local_disk_devices,
            interfaces=local_interfaces,
            acpi=self.driver.enable_acpi,
            numa=self.numa,
        )
        self.uuid = self.driver.conn.defineXML(node_xml).UUIDString()

        if self.cloud_init_volume_name is not None:
            self._create_cloudimage_settings_iso()

        super(LibvirtNode, self).define()

    def start(self):
        self.create()

    @decorators.retry(libvirt.libvirtError)
    def create(self, *args, **kwargs):
        if not self.is_active():
            self._libvirt_node.create()

    @decorators.retry(libvirt.libvirtError)
    def destroy(self, *args, **kwargs):
        if self.is_active():
            try:
                self._libvirt_node.destroy()
            except libvirt.libvirtError as e:
                if e.get_error_code() == libvirt.VIR_ERR_SYSTEM_ERROR:
                    logger.error(
                        "Error appeared while destroying the domain"
                        " {}, ignoring".format(self._libvirt_node.name()))
                    return None
                else:
                    raise
        super(LibvirtNode, self).destroy()

    @decorators.retry(libvirt.libvirtError)
    def remove(self, *args, **kwargs):
        if self.uuid:
            if self.exists():
                self.destroy()

                # EXTERNAL SNAPSHOTS
                for snapshot in self.get_snapshots():
                    snapshot.delete_snapshot_files()

                # ORIGINAL SNAPSHOTS
                if self._libvirt_node:
                    self._libvirt_node.undefineFlags(
                        libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA)
        super(LibvirtNode, self).remove()

    @decorators.retry(libvirt.libvirtError)
    def suspend(self, *args, **kwargs):
        if self.is_active():
            self._libvirt_node.suspend()
        super(LibvirtNode, self).suspend()

    @decorators.retry(libvirt.libvirtError)
    def resume(self, *args, **kwargs):
        if self._libvirt_node.info()[0] == libvirt.VIR_DOMAIN_PAUSED:
            self._libvirt_node.resume()

    @decorators.retry(libvirt.libvirtError)
    def reboot(self):
        """Reboot node

            :rtype : None
        """
        self._libvirt_node.reboot()
        super(LibvirtNode, self).reboot()

    @decorators.retry(libvirt.libvirtError)
    def shutdown(self):
        """Shutdown node

            :rtype : None
        """
        self._libvirt_node.shutdown()
        super(LibvirtNode, self).shutdown()

    @decorators.retry(libvirt.libvirtError)
    def reset(self):
        self._libvirt_node.reset()
        super(LibvirtNode, self).reset()

    @decorators.retry(libvirt.libvirtError)
    def has_snapshot(self, name):
        return name in self._libvirt_node.snapshotListNames()

    def _create_cloudimage_settings_iso(self):
        """Builds setting iso to send basic configuration for cloud image"""

        if self.cloud_init_volume_name is None:
            return
        volume = self.get_volume(name=self.cloud_init_volume_name)

        interface = self.interface_set.get(
            label=self.cloud_init_iface_up)
        admin_ip = self.get_ip_address_by_network_name(
            name=None, interface=interface)

        env_name = self.group.environment.name
        dir_path = os.path.join(settings.CLOUD_IMAGE_DIR, env_name)
        cloud_image_settings_path = os.path.join(
            dir_path, 'cloud_settings.iso')
        meta_data_path = os.path.join(dir_path, "meta-data")
        user_data_path = os.path.join(dir_path, "user-data")

        interface_name = interface.label
        admin_ap = interface.l2_network_device.address_pool
        gateway = str(admin_ap.gateway)
        admin_netmask = str(admin_ap.ip_network.netmask)
        admin_network = str(admin_ap.ip_network)
        hostname = self.name

        cloud_image_settings.generate_cloud_image_settings(
            cloud_image_settings_path=cloud_image_settings_path,
            meta_data_path=meta_data_path,
            user_data_path=user_data_path,
            admin_network=admin_network,
            interface_name=interface_name,
            admin_ip=admin_ip,
            admin_netmask=admin_netmask,
            gateway=gateway,
            hostname=hostname,
            meta_data_content=volume.cloudinit_meta_data,
            user_data_content=volume.cloudinit_user_data,
        )

        volume.upload(cloud_image_settings_path)

        # Clear temporary files
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)

    # EXTERNAL SNAPSHOT
    def snapshot_create_child_volumes(self, name):
        for disk in self.disk_devices:
            if disk.device == 'disk':

                # Find main disk name, it is used for external disk
                back_vol_name = disk.volume.name
                back_count = 0
                disk_test = disk.volume.backing_store
                while disk_test is not None:
                    back_count += 1
                    back_vol_name = disk_test.name
                    disk_test = disk_test.backing_store
                    if back_count > 500:
                        raise error.DevopsError(
                            "More then 500 snapshots in chain for {0}.{1}"
                            .format(back_vol_name, name))
                # Create new volume for snapshot
                vol_child = disk.volume.create_child(
                    name='{0}.{1}'.format(back_vol_name, name),
                )
                vol_child.define()

                # update disk node to new snapshot
                disk.volume = vol_child
                disk.save()

    # EXTERNAL SNAPSHOT
    def _assert_snapshot_type(self, external=False):
        # If domain has snapshots we must check their type

        # TODO(ddmitriev)
        snap_list = self.get_snapshots()

        if len(snap_list) > 0:
            snap_type = snap_list[0].get_type
            if external and snap_type == 'internal':
                raise error.DevopsError(
                    "Cannot create external snapshot when internal exists")
            if not external and snap_type == 'external':
                raise error.DevopsError(
                    "Cannot create internal snapshot when external exists")

    # EXTERNAL SNAPSHOT
    @decorators.retry(libvirt.libvirtError)
    def set_snapshot_current(self, name):
        snapshot = self._get_snapshot(name)

        # DOESN'T WORK if DRIVER_USE_HOST_CPU=True
        # In snapshot.xml is not appeared cpu tag <model>
        # from the snapshot XML file,
        # causing the following error:
        #   libvirtError: unsupported configuration: \
        #   Target CPU model <null> does not match source SandyBridge
        self._libvirt_node.snapshotCreateXML(
            snapshot.xml,
            libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE |
            libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT)

    @decorators.retry(libvirt.libvirtError)
    def snapshot(self, name=None, force=False, description=None,
                 disk_only=False, external=False):
        super(LibvirtNode, self).snapshot()
        # Erase existing snapshot or raise an error if already exists
        if self.has_snapshot(name):
            if force:
                self.erase_snapshot(name)
            else:
                raise error.DevopsError(
                    "Snapshot with name {0} already exists".format(name))

        # Check that existing snapshot has the same type
        self._assert_snapshot_type(external=external)

        local_disk_devices = []
        if external:
            # EXTERNAL SNAPSHOTS
            if self.driver.get_libvirt_version() < 1002012:
                raise error.DevopsError(
                    "For external snapshots we need libvirtd >= 1.2.12")

            # Check whether we have directory for snapshots, if not
            # create it
            if not os.path.exists(settings.SNAPSHOTS_EXTERNAL_DIR):
                os.makedirs(settings.SNAPSHOTS_EXTERNAL_DIR)

            # create new volume which will be used as
            # disk for snapshot changes
            self.snapshot_create_child_volumes(name)

            base_memory_file = '{0}/snapshot-memory-{1}_{2}.{3}'.format(
                settings.SNAPSHOTS_EXTERNAL_DIR,
                helpers.deepgetattr(self, 'group.environment.name'),
                self.name,
                name)
            file_count = 0
            memory_file = base_memory_file
            while os.path.exists(memory_file):
                memory_file = base_memory_file + '-' + str(file_count)
                file_count += 1

            for disk in self.disk_devices:
                if disk.device == 'disk':
                    local_disk_devices.append(dict(
                        disk_volume_path=disk.volume.get_path(),
                        disk_target_dev=disk.target_dev,
                    ))

            if self.is_active() and not disk_only:
                create_xml_flag = libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REUSE_EXT
            else:
                create_xml_flag = (
                    libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_DISK_ONLY |
                    libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_REUSE_EXT
                )

        else:
            # ORIGINAL SNAPSHOTS
            memory_file = ''
            create_xml_flag = 0

        xml = builder.LibvirtXMLBuilder.build_snapshot_xml(
            name=name,
            description=description,
            external=external,
            disk_only=disk_only,
            memory_file=memory_file,
            domain_isactive=self.is_active(),
            local_disk_devices=local_disk_devices
        )

        domain = self._libvirt_node
        logger.debug(domain.state(0))

        domain.snapshotCreateXML(xml, create_xml_flag)

        if external:
            self.set_snapshot_current(name)

        logger.debug(domain.state(0))

    # EXTERNAL SNAPSHOT
    @staticmethod
    def _delete_snapshot_files(snapshot):
        """Delete snapshot external files

        :type snapshot: Snapshot
        """
        warnings.warn(
            '_delete_snapshot_files(snapshot) has been deprecated in favor of '
            'snapshot.delete_snapshot_files()', DeprecationWarning)
        return snapshot.delete_snapshot_files()

    # EXTERNAL SNAPSHOT
    @decorators.retry(libvirt.libvirtError)
    def _redefine_external_snapshot(self, name=None):
        snapshot = self._get_snapshot(name)

        logger.info("Revert {0} ({1}) from external snapshot {2}".format(
            self.name, snapshot.state, name))

        self.destroy()

        # When snapshot dont have children we need to update disks in XML
        # used for reverting, standard revert function will restore links
        # to original disks, but we need to use disks with snapshot point,
        # we dont want to change original data
        #
        # For snapshot with children we need to create new snapshot chain
        # and we need to start from original disks, this disks will get new
        # snapshot point in node class
        # noinspection PyProtectedMember
        xml_domain = snapshot._xml_tree.find('domain')
        if snapshot.children_num == 0:
            domain_disks = xml_domain.findall('./devices/disk')
            for s_disk, s_disk_data in snapshot.disks.items():
                for d_disk in domain_disks:
                    d_disk_dev = d_disk.find('target').get('dev')
                    d_disk_device = d_disk.get('device')
                    if d_disk_dev == s_disk and d_disk_device == 'disk':
                        d_disk.find('source').set('file', s_disk_data)

        if snapshot.state == 'shutoff':
            # Redefine domain for snapshot without memory save
            self.driver.conn.defineXML(helpers.xml_tostring(xml_domain))
        else:
            self.driver.conn.restoreFlags(
                snapshot.memory_file,
                dxml=helpers.xml_tostring(xml_domain),
                flags=libvirt.VIR_DOMAIN_SAVE_PAUSED)

        # set snapshot as current
        self.set_snapshot_current(name)

    def _update_disks_from_snapshot(self, name):
        """Update actual node disks volumes to disks from snapshot

           This method change disks attached to actual node to
           disks used in snapshot. This is required to save correct
           state of node disks. We use node disks as a backend when
           new snapshots are created.
        """
        snapshot = self._get_snapshot(name)

        for snap_disk, snap_disk_file in snapshot.disks.items():
            for disk in self.disk_devices:
                if snap_disk == disk.target_dev:
                    if snapshot.children_num == 0:
                        disk.volume = self.get_volume(uuid=snap_disk_file)
                    else:
                        disk.volume = self.get_volume(
                            uuid=snap_disk_file).backing_store
                    disk.save()

    @decorators.retry(libvirt.libvirtError)
    def _node_revert_snapshot_recreate_disks(self, name):
        """Recreate snapshot disks."""
        snapshot = self._get_snapshot(name)

        if snapshot.children_num == 0:
            for s_disk_data in snapshot.disks.values():
                logger.info("Recreate {0}".format(s_disk_data))

                # Save actual volume XML, delete volume and create
                # new from saved XML
                volume = self.driver.conn.storageVolLookupByKey(s_disk_data)
                volume_xml = volume.XMLDesc()
                volume_pool = volume.storagePoolLookupByVolume()
                volume.delete()
                volume_pool.createXML(volume_xml)

    def _revert_external_snapshot(self, name=None):
        snapshot = self._get_snapshot(name)
        self.destroy()
        if snapshot.children_num == 0:
            logger.info("Reuse last snapshot")

            # Update current node disks
            self._update_disks_from_snapshot(name)

            # Recreate volumes for snapshot and reuse it.
            self._node_revert_snapshot_recreate_disks(name)

            # Revert snapshot
            # self.driver.node_revert_snapshot(node=self, name=name)
            self._redefine_external_snapshot(name=name)
        else:
            # Looking for last reverted snapshot without children
            # or create new and start next snapshot chain
            revert_name = name + '-revert'
            revert_count = 0
            create_new = True

            while self.has_snapshot(revert_name):
                # Check wheter revert snapshot has children
                snapshot_revert = self._get_snapshot(revert_name)
                if snapshot_revert.children_num == 0:
                    logger.info(
                        "Revert snapshot exists, clean and reuse it")

                    # Update current node disks
                    self._update_disks_from_snapshot(revert_name)

                    # Recreate volumes
                    self._node_revert_snapshot_recreate_disks(revert_name)

                    # Revert snapshot
                    # self.driver.node_revert_snapshot(
                    #    node=self, name=revert_name)
                    self._redefine_external_snapshot(name=revert_name)
                    create_new = False
                    break
                else:
                    revert_name = name + '-revert' + str(revert_count)
                    revert_count += 1

            if create_new:
                logger.info("Create new revert snapshot")

                # Update current node disks
                self._update_disks_from_snapshot(name)

                # Revert snapshot
                # self.driver.node_revert_snapshot(node=self, name=name)
                self._redefine_external_snapshot(name=name)

                # Create new snapshot
                self.snapshot(name=revert_name, external=True)

    @decorators.retry(libvirt.libvirtError)
    def revert(self, name=None):
        """Method to revert node in state from snapshot

           For external snapshots in libvirt we use restore function.
           After reverting in this way we get situation when node is connected
           to original volume disk, without snapshot point. To solve this
           problem we need to switch it to correct volume.

           In case of usage external snapshots we clean snapshot disk when
           revert to snapshot without childs and create new snapshot point
           when reverting to snapshots with childs.
        """
        if self.has_snapshot(name):
            snapshot = self._get_snapshot(name)

            if snapshot.get_type == 'external':
                # EXTERNAL SNAPSHOT
                self._revert_external_snapshot(name)
            else:
                # ORIGINAL SNAPSHOT
                logger.info("Revert {0} ({1}) to internal snapshot {2}".format(
                    self.name, snapshot.state, name))
                # noinspection PyProtectedMember
                self._libvirt_node.revertToSnapshot(snapshot._snapshot, 0)

        else:
            raise error.DevopsError(
                'Domain snapshot for {0} node not found: no domain '
                'snapshot with matching'
                ' name {1}'.format(self.name, name))

        # unblock all interfaces
        for iface in self.interfaces:
            if iface.is_blocked:
                logger.info("Interface({}) in {} network has "
                            "been unblocked".format(
                                iface.mac_address,
                                iface.l2_network_device.name))
                iface.unblock()

    @decorators.retry(libvirt.libvirtError)
    def _get_snapshot(self, name):
        """Get snapshot

        :type name: String
            :rtype : Snapshot(libvirt.virDomainSnapshot)
        """
        if name is None:
            return Snapshot(self._libvirt_node.snapshotCurrent(0))
        else:
            return Snapshot(self._libvirt_node.snapshotLookupByName(name, 0))

    @decorators.retry(libvirt.libvirtError)
    def get_snapshots(self):
        """Return full snapshots objects"""
        snapshots = self._libvirt_node.listAllSnapshots(0)
        return [Snapshot(snap) for snap in snapshots]

    @decorators.retry(libvirt.libvirtError)
    def erase_snapshot(self, name):
        if self.has_snapshot(name):

            snapshot = self._get_snapshot(name)
            snap_type = snapshot.get_type
            if snap_type == 'external':
                # EXTERNAL SNAPSHOT DELETE
                if snapshot.children_num > 0:
                    logger.error("Cannot delete external snapshots "
                                 "with children")
                    return

                self.destroy()

                # Update domain to snapshot state
                # noinspection PyProtectedMember
                xml_domain = snapshot._xml_tree.find('domain')
                self.driver.conn.defineXML(helpers.xml_tostring(xml_domain))
                snapshot.delete_snapshot_files()
                snapshot.delete(2)

                for disk in self.disk_devices:
                    if disk.device == 'disk':
                        snap_disk = disk.volume
                        # update disk on node
                        disk.volume = disk.volume.backing_store
                        disk.save()
                        snap_disk.remove()

            else:
                # ORIGINAL DELETE
                snapshot.delete(0)

    def set_vcpu(self, vcpu):
        """Set vcpu count on node

        param: vcpu: Integer
            :rtype : None
        """
        if vcpu is not None and vcpu != self.vcpu:
            self.vcpu = vcpu
            domain = self._libvirt_node
            domain.setVcpusFlags(vcpu, 4)
            domain.setVcpusFlags(vcpu, 2)
            self.save()

    def set_memory(self, memory):
        """Set memory size on node

        param: memory: Integer
            :rtype : None
        """
        if memory is not None and memory != self.memory:
            self.memory = memory
            domain = self._libvirt_node
            domain.setMaxMemory(memory * 1024)
            domain.setMemoryFlags(memory * 1024, 2)
            self.save()

    @decorators.retry(libvirt.libvirtError)
    def get_interface_target_dev(self, mac):
        """Get target device

        :type mac: String
            :rtype : String
        """
        xml_desc = ET.fromstring(self._libvirt_node.XMLDesc(0))
        target = xml_desc.find('.//mac[@address="%s"]/../target' % mac)
        if target is not None:
            return target.get('dev')

    def attach_volume(self, volume, device='disk', type='file',
                      bus='virtio', target_dev=None):
        """Attach volume to node

        :rtype : DiskDevice
        """
        cls = self.driver.get_model_class('DiskDevice')

        if volume.multipath_count:
            for _ in range(volume.multipath_count):
                cls.objects.create(
                    device=device, type=type, bus='scsi',
                    target_dev=target_dev or self.next_disk_name(),
                    volume=volume, node=self)
        else:
            return cls.objects.create(
                device=device, type=type, bus=bus,
                target_dev=target_dev or self.next_disk_name(),
                volume=volume, node=self)

    @decorators.retry(libvirt.libvirtError)
    def set_boot(self, boot):
        """Set boot order on node

        :type boot: list
        :rtype: None
        """
        domain_xml = ET.fromstring(self._libvirt_node.XMLDesc())
        os_el = domain_xml.find('./os')
        old_boot = os_el.findall('boot[@dev]')

        # remove old boot
        for boot_el in old_boot:
            os_el.remove(boot_el)

        # add new boot
        for boot_dev in boot:
            os_el.append(ET.Element('boot', dev=boot_dev))

        # apply changes to domain
        self.driver.conn.defineXML(helpers.xml_tostring(domain_xml))

        self.boot = boot
        self.save()

    @decorators.retry(libvirt.libvirtError)
    def close_tray(self):
        """Closes tray for all cdrom devices

        :rtype: None
        """
        domain_xml = ET.fromstring(self._libvirt_node.XMLDesc())

        # find all target elements
        target_els = domain_xml.findall(
            './devices/disk[@device="cdrom"]/target')

        for target_el in target_els:
            # set tray to closed
            target_el.attrib['tray'] = 'closed'

        if target_els:
            # apply changes to domain
            self.driver.conn.defineXML(helpers.xml_tostring(domain_xml))
        else:
            logger.warning("Can't close tray: no cdrom devices "
                           "found for Node {!r}".format(self.name))


class LibvirtInterface(network.Interface):

    @decorators.retry(libvirt.libvirtError)
    def define(self):
        if self.driver.enable_nwfilters:
            filter_xml = builder.LibvirtXMLBuilder.build_interface_filter(
                name=self.nwfilter_name,
                filterref=self.l2_network_device.network_name)
            self.driver.conn.nwfilterDefineXML(filter_xml)

        super(LibvirtInterface, self).define()

    @decorators.retry(libvirt.libvirtError)
    def remove(self):
        if self.driver.enable_nwfilters:
            if self._nwfilter:
                self._nwfilter.undefine()
        super(LibvirtInterface, self).remove()

    @property
    def nwfilter_name(self):
        return helpers.underscored(
            self.node.group.environment.name,
            self.l2_network_device.name,
            self.mac_address)

    @property
    @decorators.retry(libvirt.libvirtError)
    def _nwfilter(self):
        try:
            return self.driver.conn.nwfilterLookupByName(self.nwfilter_name)
        except libvirt.libvirtError:
            logger.error("NWFilter not found by name: {}".format(
                self.nwfilter_name))

    @property
    @decorators.retry(libvirt.libvirtError)
    def is_blocked(self):
        """Show state of interface"""
        if not self.driver.enable_nwfilters:
            return False
        if not self._nwfilter:
            return False

        filter_xml = ET.fromstring(self._nwfilter.XMLDesc())
        return filter_xml.find('./rule') is not None

    @decorators.retry(libvirt.libvirtError)
    def block(self):
        """Block traffic on interface"""
        if not self.driver.enable_nwfilters:
            return
        if not self._nwfilter:
            raise error.DevopsError(
                "Unable to block interface {} on node {}: nwfilter not"
                " found!".format(self.label, self.node.name))

        filter_xml = builder.LibvirtXMLBuilder.build_interface_filter(
            name=self.nwfilter_name,
            filterref=self.l2_network_device.network_name,
            uuid=self._nwfilter.UUIDString(),
            rule=dict(
                action='drop',
                direction='inout',
                priority='-950'))
        self.driver.conn.nwfilterDefineXML(filter_xml)

    @decorators.retry(libvirt.libvirtError)
    def unblock(self):
        """Unblock traffic on interface"""
        if not self.driver.enable_nwfilters:
            return
        if not self._nwfilter:
            raise error.DevopsError(
                "Unable to unblock interface {} on node {}: nwfilter not"
                " found!".format(self.label, self.node.name))

        filter_xml = builder.LibvirtXMLBuilder.build_interface_filter(
            name=self.nwfilter_name,
            filterref=self.l2_network_device.network_name,
            uuid=self._nwfilter.UUIDString())
        self.driver.conn.nwfilterDefineXML(filter_xml)


class LibvirtDiskDevice(volume.DiskDevice):

    device = base.ParamField(default='disk', choices=('disk', 'cdrom'))
    type = base.ParamField(default='file', choices='file')
    bus = base.ParamField(default='virtio', choices=('virtio', 'ide', 'scsi'))
    target_dev = base.ParamField()

    @property
    def multipath_enabled(self):
        return self.volume.multipath_count > 0
