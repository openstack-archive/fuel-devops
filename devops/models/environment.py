#    Copyright 2013 - 2015 Mirantis, Inc.
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

from django.conf import settings
from django.db import models
from ipaddr import IPNetwork

from devops.helpers.helpers import _get_file_size
from devops import logger
from devops.models.base import DriverModel
from devops.models.network import DiskDevice
from devops.models.network import Interface
from devops.models.network import Network
from devops.models.node import Node
from devops.models.volume import Volume


class Environment(DriverModel):
    class Meta:
        db_table = 'devops_environment'

    name = models.CharField(max_length=255, unique=True, null=False)

    hostname = 'nailgun'
    domain = 'test.domain.local'
    nat_interface = ''  # INTERFACES.get('admin')
    admin_net = 'admin'
    admin_net2 = 'admin2'
    os_image = None  # Dirty hack. Check for os_image attribute for relevancy.

    def get_volume(self, *args, **kwargs):
        return self.volume_set.get(*args, **kwargs)

    def get_volumes(self, *args, **kwargs):
        return self.volume_set.filter(*args, **kwargs)

    def get_network(self, *args, **kwargs):
        return self.network_set.get(*args, **kwargs)

    def get_networks(self, *args, **kwargs):
        return self.network_set.filter(*args, **kwargs)

    def get_node(self, *args, **kwargs):
        return self.node_set.get(*args, **kwargs)

    def get_nodes(self, *args, **kwargs):
        return self.node_set.filter(*args, **kwargs)

    def add_node(self, memory, name, vcpu=1, boot=None):
        return Node.node_create(
            name=name,
            memory=memory,
            vcpu=vcpu,
            environment=self,
            boot=boot)

    def add_empty_volume(self, node, name,
                         capacity=settings.NODE_VOLUME_SIZE * 1024 * 1024
                         * 1024, device='disk', bus='virtio', format='qcow2'):
        DiskDevice.node_attach_volume(
            node=node,
            volume=Volume.volume_create(
                name=name,
                capacity=capacity,
                environment=self,
                format=format),
            device=device,
            bus=bus)

    @classmethod
    def create(cls, name):
        """Create Environment instance with given name.

        :rtype: devops.models.Environment
        """
        return cls.objects.create(name=name)

    @classmethod
    def get(cls, *args, **kwargs):
        return cls.objects.get(*args, **kwargs)

    @classmethod
    def list(cls):
        return cls.objects.all()

    def has_snapshot(self, name):
        return all(map(lambda x: x.has_snapshot(name), self.get_nodes()))

    def define(self):
        for network in self.get_networks():
            network.define()
        for volume in self.get_volumes():
            volume.define()
        for node in self.get_nodes():
            node.define()

    def start(self, nodes=None):
        for network in self.get_networks():
            network.start()
        for node in nodes or self.get_nodes():
            node.start()

    def destroy(self, verbose=False):
        for node in self.get_nodes():
            node.destroy(verbose=verbose)

    def erase(self):
        for node in self.get_nodes():
            node.erase()
        for network in self.get_networks():
            network.erase()
        for volume in self.get_volumes():
            volume.erase()
        self.delete()

    @classmethod
    def erase_empty(cls):
        for env in cls.objects.all():
            if len(env.get_nodes()) == 0:
                env.delete()

    def suspend(self, verbose=False):
        for node in self.get_nodes():
            node.suspend(verbose)

    def resume(self, verbose=False):
        for node in self.get_nodes():
            node.resume(verbose)

    def snapshot(self, name=None, description=None, force=False):
        for node in self.get_nodes():
            node.snapshot(name=name, description=description, force=force)

    def revert(self, name=None, destroy=True, flag=True):
        if destroy:
            for node in self.get_nodes():
                node.destroy(verbose=False)
        if (flag and not all(
                [node.has_snapshot(name) for node in self.get_nodes()])):
            raise Exception("some nodes miss snapshot,"
                            " test should be interrupted")
        for node in self.get_nodes():
            node.revert(name, destroy=False)

    @classmethod
    def synchronize_all(cls):
        driver = cls.get_driver()
        nodes = {driver._get_name(e.name, n.name): n
                 for e in cls.objects.all()
                 for n in e.get_nodes()}
        domains = set(driver.node_list())

        # FIXME (AWoodward) This willy nilly wacks domains when you run this
        #  on domains that are outside the scope of devops, if anything this
        #  should cause domains to be imported into db instead of undefined.
        #  It also leaves network and volumes around too
        #  Disabled untill a safer implmentation arrives

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

        logger.info('Undefined domains: %s, removed nodes: %s' %
                    (0, len(nodes_to_remove)))

    @classmethod
    def describe_environment(cls):
        environment = cls.create(settings.ENV_NAME)
        networks = []
        interfaces = settings.INTERFACE_ORDER
        if settings.MULTIPLE_NETWORKS:
            logger.info('Multiple cluster networks feature is enabled!')
        if settings.BONDING:
            interfaces = settings.BONDING_INTERFACES.keys()

        for name in interfaces:
            networks.append(environment.create_networks(name))
        for name in environment.node_roles.admin_names:
            environment.describe_admin_node(name, networks)
        for num, name in enumerate(environment.node_roles.other_names):
            if settings.MULTIPLE_NETWORKS:
                networks1 = [net for net in networks if net.name
                             in settings.NODEGROUPS[0]['pools']]
                networks2 = [net for net in networks if net.name
                             in settings.NODEGROUPS[1]['pools']]
                # If slave index is even number, then attach to
                # it virtual networks from the second network group.
                if int(num) % 2 == 0:
                    environment.describe_empty_node(name, networks1)
                else:
                    environment.describe_empty_node(name, networks2)
            else:
                environment.describe_empty_node(name, networks)
        return environment

    def create_networks(self, name):
        ip_networks = [
            IPNetwork(x) for x in settings.POOLS.get(name)[0].split(',')]
        new_prefix = int(settings.POOLS.get(name)[1])
        pool = Network.create_network_pool(networks=ip_networks,
                                           prefix=int(new_prefix))
        return Network.network_create(
            name=name,
            environment=self,
            pool=pool,
            forward=settings.FORWARDING.get(name),
            has_dhcp_server=settings.DHCP.get(name))

    def create_interfaces(self, networks, node,
                          model=settings.INTERFACE_MODEL):
        if settings.BONDING:
            for network in networks:
                Interface.interface_create(
                    network, node=node, model=model,
                    interface_map=settings.BONDING_INTERFACES)
        else:
            for network in networks:
                Interface.interface_create(network, node=node, model=model)

    @property
    def node_roles(self):
        return NodeRoles(
            admin_names=['admin'],
            other_names=['slave'] * int(settings.NODES_COUNT)
        )

    def _rename_with_mac(self, node):
        name = node.name
        mac = node.get_interface(
            node=node,
            network=self.get_network(
                environment=self,
                name__contains=self.admin_net)
        ).mac_address[-5:].replace(':', '-')

        node.name = "{0}_{1}".format(name, mac)
        node.save()
        return node.name

    def describe_empty_node(self, name, networks):
        node = self.add_node(
            name=name,
            memory=settings.HARDWARE.get("slave_node_memory", 1024),
            vcpu=settings.HARDWARE.get("slave_node_cpu", 1))
        self.create_interfaces(networks, node)
        name = self._rename_with_mac(node)
        self.add_empty_volume(node, name + '-system')

        if settings.USE_ALL_DISKS:
            self.add_empty_volume(node, name + '-cinder')
            self.add_empty_volume(node, name + '-swift')

        return node

    # @logwrap
    def describe_admin_node(self, name, networks):
        node = self.add_node(
            memory=settings.HARDWARE.get("admin_node_memory", 1024),
            vcpu=settings.HARDWARE.get("admin_node_cpu", 1),
            name=name,
            boot=['hd', 'cdrom'])
        self.create_interfaces(networks, node)

        if self.os_image is None:
            self.add_empty_volume(node, name + '-system')
            self.add_empty_volume(
                node,
                name + '-iso',
                capacity=_get_file_size(settings.ISO_PATH),
                format='raw',
                device='cdrom',
                bus='ide')
        else:
            volume = Volume.volume_get_predefined(self.os_image)
            vol_child = Volume.volume_create_child(
                name=name + '-system',
                backing_store=volume,
                environment=self.get_virtual_environment()
            )
            DiskDevice.node_attach_volume(
                node=node,
                volume=vol_child
            )
        return node

    def router(self, router_name=None):  # Alternative name: get_host_node_ip
        router_name = router_name or self.admin_net
        if router_name == self.admin_net2:
            return str(IPNetwork(self.get_virtual_environment().
                                 get_network(name=router_name).ip_network)[2])
        return str(
            IPNetwork(self.get_network(name=router_name).ip_network)[1])

    def nodes(self):  # migrated from EnvironmentModel.nodes()
        return Nodes(self, self.node_roles)


class NodeRoles(object):
    def __init__(self,
                 admin_names=None,
                 other_names=None):
        self.admin_names = admin_names or []
        self.other_names = other_names or []


class Nodes(object):
    def __init__(self, environment, node_roles):
        self.admins = []
        self.others = []
        for node_name in node_roles.admin_names:
            self.admins.append(environment.get_node(name=node_name))
        self.others = list(set(environment.get_nodes()) - set(self.admins))
        self.slaves = self.others
        self.all = self.slaves + self.admins
        self.admin = self.admins[0]

    def __iter__(self):
        return self.all.__iter__()
