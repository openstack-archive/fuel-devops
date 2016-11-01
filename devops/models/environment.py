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

import time
import warnings

from django.conf import settings
from django.db import IntegrityError
from django.db import models
import netaddr
import paramiko

from devops import error
from devops.helpers import network as network_helpers
from devops.helpers import ssh_client
from devops import logger
from devops.models import base
from devops.models import driver
from devops.models import group
from devops.models import network
from devops.models import node


class Environment(base.BaseModel):
    class Meta(object):
        db_table = 'devops_environment'
        app_label = 'devops'

    name = models.CharField(max_length=255, unique=True, null=False)

    def __repr__(self):
        return 'Environment(name={name!r})'.format(name=self.name)

    @property
    def admin_net(self):
        msg = (
            'Environment.admin_net is deprecated. '
            'Replace by string "admin".'
        )
        logger.warning(msg)
        warnings.warn(msg, DeprecationWarning)
        return 'admin'

    @property
    def admin_net2(self):
        msg = (
            'Environment.admin_net2 is deprecated. '
            'Replace by string "admin2".'
        )
        logger.warning(msg)
        warnings.warn(msg, DeprecationWarning)
        return 'admin2'

    @property
    def nat_interface(self):
        msg = (
            'Environment.nat_interface is deprecated.'
        )
        logger.warning(msg)
        warnings.warn(msg, DeprecationWarning)
        return ''

    def get_allocated_networks(self):
        allocated_networks = []
        for grp in self.get_groups():
            allocated_networks += grp.get_allocated_networks()
        return allocated_networks

    def get_address_pool(self, **kwargs):
        try:
            return self.addresspool_set.get(**kwargs)
        except network.AddressPool.DoesNotExist:
            raise error.DevopsObjNotFound(network.AddressPool, **kwargs)

    def get_address_pools(self, **kwargs):
        return self.addresspool_set.filter(**kwargs).order_by('id')

    def get_group(self, **kwargs):
        try:
            return self.group_set.get(**kwargs)
        except group.Group.DoesNotExist:
            raise error.DevopsObjNotFound(group.Group, **kwargs)

    def get_groups(self, **kwargs):
        return self.group_set.filter(**kwargs).order_by('id')

    def add_groups(self, groups):
        for group_data in groups:
            driver_data = group_data['driver']
            if driver_data['name'] == 'devops.driver.libvirt.libvirt_driver':
                warnings.warn(
                    "Driver 'devops.driver.libvirt.libvirt_driver' "
                    "has been renamed to 'devops.driver.libvirt', "
                    "please update the tests!",
                    DeprecationWarning)
                logger.warning(
                    "Driver 'devops.driver.libvirt.libvirt_driver' "
                    "has been renamed to 'devops.driver.libvirt', "
                    "please update the tests!")
                driver_data['name'] = 'devops.driver.libvirt'
            self.add_group(
                group_name=group_data['name'],
                driver_name=driver_data['name'],
                **driver_data.get('params', {})
            )

    def add_group(self, group_name, driver_name, **driver_params):
        drv = driver.Driver.driver_create(
            name=driver_name,
            **driver_params
        )
        return group.Group.group_create(
            name=group_name,
            environment=self,
            driver=drv,
        )

    def add_address_pools(self, address_pools):
        for name, data in address_pools.items():
            self.add_address_pool(
                name=name,
                net=data['net'],
                **data.get('params', {})
            )

    def add_address_pool(self, name, net, **params):

        networks, prefix = net.split(':')
        ip_networks = [netaddr.IPNetwork(x) for x in networks.split(',')]

        pool = network_helpers.IpNetworksPool(
            networks=ip_networks,
            prefix=int(prefix),
            allocated_networks=self.get_allocated_networks())

        return network.AddressPool.address_pool_create(
            environment=self,
            name=name,
            pool=pool,
            **params
        )

    @classmethod
    def create(cls, name):
        """Create Environment instance with given name.

        :rtype: devops.models.Environment
        """
        try:
            return cls.objects.create(name=name)
        except IntegrityError:
            raise error.DevopsError(
                'Environment with name {!r} already exists. '
                'Please, set another environment name.'
                ''.format(name))

    @classmethod
    def get(cls, *args, **kwargs):
        try:
            return cls.objects.get(*args, **kwargs)
        except Environment.DoesNotExist:
            raise error.DevopsObjNotFound(Environment, *args, **kwargs)

    @classmethod
    def list_all(cls):
        return cls.objects.all()

    # LEGACY
    def has_snapshot(self, name):
        if self.get_nodes():
            return all(n.has_snapshot(name) for n in self.get_nodes())
        else:
            return False

    def define(self):
        for grp in self.get_groups():
            grp.define_networks()
        for grp in self.get_groups():
            grp.define_volumes()
        for grp in self.get_groups():
            grp.define_nodes()

    def start(self, nodes=None):
        for grp in self.get_groups():
            grp.start_networks()
        for grp in self.get_groups():
            grp.start_nodes(nodes)

    def destroy(self):
        for grp in self.get_groups():
            grp.destroy()

    def erase(self):
        for grp in self.get_groups():
            grp.erase()
        self.delete()

    def suspend(self, **kwargs):
        for nod in self.get_nodes():
            nod.suspend()

    def resume(self, **kwargs):
        for nod in self.get_nodes():
            nod.resume()

    def snapshot(self, name=None, description=None, force=False, suspend=True):
        """Snapshot the environment

        :param name: name of the snapshot. Current timestamp, if name is None
        :param description: any string that will be placed to the 'description'
                            section in the snapshot XML
        :param force: If True - overwrite the existing snapshot. Default: False
        :param suspend: suspend environment before snapshot if True (default)
        """
        if name is None:
            name = str(int(time.time()))
        if self.has_snapshot(name) and not force:
            raise error.DevopsError(
                'Snapshot with name {0} already exists.'.format(
                    self.params.snapshot_name))
        if suspend:
            for nod in self.get_nodes():
                nod.suspend()

        for nod in self.get_nodes():
            nod.snapshot(name=name, description=description, force=force,
                         external=settings.SNAPSHOTS_EXTERNAL)

    def revert(self, name=None, flag=True, resume=True):
        """Revert the environment from snapshot

        :param name: name of the snapshot
        :param flag: raise Exception if True (default) and snapshot not found
        :param resume: resume environment after revert if True (default)
        """
        if flag and not self.has_snapshot(name):
            raise Exception("some nodes miss snapshot,"
                            " test should be interrupted")
        for nod in self.get_nodes():
            nod.revert(name)

        for grp in self.get_groups():
            for l2netdev in grp.get_l2_network_devices():
                l2netdev.unblock()

        if resume:
            for nod in self.get_nodes():
                nod.resume(name)

    # NOTE: Does not work
    # TO REWRITE FOR LIBVIRT DRIVER ONLY
    @classmethod
    def synchronize_all(cls):
        driver = cls.get_driver()
        nodes = {driver._get_name(e.name, n.name): n
                 for e in cls.list_all()
                 for n in e.get_nodes()}
        domains = set(driver.node_list())

        # FIXME (AWoodward) This willy nilly wacks domains when you run this
        #  on domains that are outside the scope of devops, if anything this
        #  should cause domains to be imported into db instead of undefined.
        #  It also leaves network and volumes around too
        #  Disabled until a safer implementation arrives

        # Undefine domains without devops nodes
        #
        # domains_to_undefine = domains - set(nodes.keys())
        # for d in domains_to_undefine:
        #    driver.node_undefine_by_name(d)

        # Remove devops nodes without domains
        nodes_to_remove = set(nodes.keys()) - domains
        for n in nodes_to_remove:
            nodes[n].delete()
        cls.erase_empty()

        logger.info('Undefined domains: {0}, removed nodes: {1}'.format(
            0, len(nodes_to_remove)
        ))

    # LEGACY
    @classmethod
    def describe_environment(cls, boot_from='cdrom'):
        """This method is DEPRECATED.

           Reserved for backward compatibility only.
           Please use self.create_environment() instead.
        """
        warnings.warn(
            'describe_environment is deprecated in favor of '
            'DevopsClient.create_env_from_config', DeprecationWarning)

        from devops import client
        dclient = client.DevopsClient()

        template = settings.DEVOPS_SETTINGS_TEMPLATE
        if template:
            return dclient.create_env_from_config(template)
        else:
            return dclient.create_env()

    @classmethod
    def create_environment(cls, full_config):
        """Create a new environment using full_config object

        :param full_config: object that describes all the parameters of
                            created environment

        :rtype: Environment
        """

        config = full_config['template']['devops_settings']
        environment = cls.create(config['env_name'])

        try:
            # create groups and drivers
            groups = config['groups']
            environment.add_groups(groups)

            # create address pools
            address_pools = config['address_pools']
            environment.add_address_pools(address_pools)

            # process group items
            for group_data in groups:
                group = environment.get_group(name=group_data['name'])

                # add l2_network_devices
                group.add_l2_network_devices(
                    group_data.get('l2_network_devices', {}))

                # add network_pools
                group.add_network_pools(
                    group_data.get('network_pools', {}))

            # Connect nodes to already created networks
            for group_data in groups:
                group = environment.get_group(name=group_data['name'])

                # add group volumes
                group.add_volumes(
                    group_data.get('group_volumes', []))

                # add nodes
                group.add_nodes(
                    group_data.get('nodes', []))
        except Exception:
            logger.error("Creation of the environment '{0}' failed"
                         .format(config['env_name']))
            environment.erase()
            raise

        return environment

    # LEGACY - TO MODIFY BY GROUPS
    @classmethod
    def erase_empty(cls):
        for env in cls.list_all():
            if env.get_nodes().count() == 0:
                env.erase()

    # LEGACY, TO REMOVE
    def router(self, router_name='admin'):
        msg = ('router has been deprecated in favor of '
               'DevopsEnvironment.get_default_gw')
        logger.warning(msg)
        warnings.warn(msg, DeprecationWarning)

        from devops.client import DevopsClient
        env = DevopsClient().get_env(self.name)
        return env.get_default_gw(l2_network_device_name=router_name)

    # LEGACY, for fuel-qa compatibility
    # @logwrap
    def get_admin_remote(self,
                         login=settings.SSH_CREDENTIALS['login'],
                         password=settings.SSH_CREDENTIALS['password']):
        """SSH to admin node

        :rtype : SSHClient
        """
        msg = ('get_admin_remote has been deprecated in favor of '
               'DevopsEnvironment.get_admin_remote')
        logger.warning(msg)
        warnings.warn(msg, DeprecationWarning)

        from devops import client
        env = client.DevopsClient().get_env(self.name)
        return env.get_admin_remote(login=login, password=password)

    # LEGACY,  for fuel-qa compatibility
    # @logwrap
    def get_ssh_to_remote(self, ip,
                          login=settings.SSH_SLAVE_CREDENTIALS['login'],
                          password=settings.SSH_SLAVE_CREDENTIALS['password']):
        msg = ('get_ssh_to_remote has been deprecated in favor of '
               'DevopsEnvironment.get_node_remote')
        logger.warning(msg)
        warnings.warn(msg, DeprecationWarning)

        from devops import client
        env = client.DevopsClient().get_env(self.name)
        return ssh_client.SSHClient(
            ip,
            auth=ssh_client.SSHAuth(
                username=login, password=password,
                keys=env.get_private_keys()))

    # LEGACY,  for fuel-qa compatibility
    # @logwrap
    @staticmethod
    def get_ssh_to_remote_by_key(ip, keyfile):
        warnings.warn('LEGACY,  for fuel-qa compatibility', DeprecationWarning)
        try:
            with open(keyfile) as f:
                keys = [paramiko.RSAKey.from_private_key(f)]
        except IOError:
            logger.warning('Loading of SSH key from file failed. Trying to use'
                           ' SSH agent ...')
            keys = paramiko.Agent().get_keys()
        return ssh_client.SSHClient(
            ip,
            auth=ssh_client.SSHAuth(keys=keys))

    # LEGACY, TO REMOVE (for fuel-qa compatibility)
    def nodes(self):  # migrated from EnvironmentModel.nodes()
        warnings.warn(
            'environment.nodes is deprecated in favor of'
            ' environment.get_nodes', DeprecationWarning)
        # DEPRECATED. Please use environment.get_nodes() instead.

        class Nodes(object):
            def __init__(self, environment):
                self.admins = sorted(
                    list(environment.get_nodes(role__contains='master')),
                    key=lambda node: node.name
                )
                self.others = sorted(
                    list(environment.get_nodes(role='fuel_slave')),
                    key=lambda node: node.name
                )
                self.ironics = sorted(
                    list(environment.get_nodes(role='ironic')),
                    key=lambda node: node.name
                )
                self.slaves = self.others
                self.all = self.slaves + self.admins + self.ironics
                if len(self.admins) == 0:
                    raise error.DevopsEnvironmentError(
                        "No nodes with role 'fuel_master' found in the "
                        "environment {env_name}, please check environment "
                        "configuration".format(
                            env_name=environment.name
                        ))
                self.admin = self.admins[0]

            def __iter__(self):
                return self.all.__iter__()

        return Nodes(self)

    # BACKWARD COMPATIBILITY LAYER
    def _create_network_object(self, l2_network_device):
        class LegacyNetwork(object):
            def __init__(self):
                self.id = l2_network_device.id
                self.name = l2_network_device.name
                self.uuid = l2_network_device.uuid
                self.environment = self
                self.has_dhcp_server = l2_network_device.dhcp
                self.has_pxe_server = l2_network_device.has_pxe_server
                self.has_reserved_ips = True
                self.tftp_root_dir = ''
                self.forward = l2_network_device.forward.mode
                self.net = l2_network_device.address_pool.net
                self.ip_network = l2_network_device.address_pool.net
                self.ip = l2_network_device.address_pool.ip_network
                self.ip_pool_start = (
                    l2_network_device.address_pool.ip_network[2])
                self.ip_pool_end = (
                    l2_network_device.address_pool.ip_network[-2])
                self.netmask = (
                    l2_network_device.address_pool.ip_network.netmask)
                self.default_gw = l2_network_device.address_pool.ip_network[1]

        return LegacyNetwork()

    def get_env_l2_network_device(self, **kwargs):
        try:
            return network.L2NetworkDevice.objects.get(
                group__environment=self, **kwargs)
        except network.L2NetworkDevice.DoesNotExist:
            raise error.DevopsObjNotFound(network.L2NetworkDevice, **kwargs)

    def get_env_l2_network_devices(self, **kwargs):
        return network.L2NetworkDevice.objects.filter(
            group__environment=self, **kwargs).order_by('id')

    # LEGACY, TO CHECK IN fuel-qa / PROXY
    def get_network(self, **kwargs):
        l2_network_device = self.get_env_l2_network_device(
            address_pool__isnull=False, **kwargs)
        return self._create_network_object(l2_network_device)

    # LEGACY, TO CHECK IN fuel-qa / PROXY
    def get_networks(self, **kwargs):
        l2_network_devices = self.get_env_l2_network_devices(
            address_pool__isnull=False, **kwargs)
        return [self._create_network_object(x) for x in l2_network_devices]

    def get_node(self, *args, **kwargs):
        try:
            return node.Node.objects.get(
                *args, group__environment=self, **kwargs)
        except node.Node.DoesNotExist:
            raise error.DevopsObjNotFound(node.Node, *args, **kwargs)

    def get_nodes(self, *args, **kwargs):
        return node.Node.objects.filter(
            *args, group__environment=self, **kwargs).order_by('id')
