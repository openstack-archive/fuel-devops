#    Copyright 2013 Mirantis, Inc.
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

import json
from os import environ

environ.setdefault("DJANGO_SETTINGS_MODULE", "devops.settings")

from django.db import IntegrityError
from django.db import transaction
import ipaddr

from devops.helpers.helpers import generate_mac
from devops.helpers.network import IpNetworksPool
from devops.models import Address
from devops.models import DiskDevice
from devops.models import Environment
from devops.models import ExternalModel
from devops.models import Interface
from devops.models import Network
from devops.models import Node
from devops.models import Volume


class Manager(object):
    def __init__(self):
        super(Manager, self).__init__()
        self.default_pool = None

    def environment_create(self, name):
        """Create environment

        :rtype : Environment
        """
        return Environment.objects.create(name=name)

    def environment_list(self):
        return Environment.objects.all()

    def environment_get(self, name):
        """Get environment by name

        :rtype : Environment
        """
        return Environment.objects.get(name=name)

    def create_network_pool(self, networks, prefix):
        """Create network pool

        :rtype : IpNetworksPool
        """
        pool = IpNetworksPool(networks=networks, prefix=prefix)
        pool.set_allocated_networks(ExternalModel.get_allocated_networks())
        return pool

    def _get_default_pool(self):
        """Get default pool. If it does not exists, create 10.0.0.0/16 pool.

        :rtype : IpNetworksPool
        """
        self.default_pool = self.default_pool or self.create_network_pool(
            networks=[ipaddr.IPNetwork('10.0.0.0/16')],
            prefix=24)
        return self.default_pool

    @transaction.commit_on_success
    def _safe_create_network(
            self, name, environment=None, pool=None,
            has_dhcp_server=True, has_pxe_server=False,
            forward='nat'):
        allocated_pool = pool or self._get_default_pool()
        while True:
            try:
                ip_network = allocated_pool.next()
                if not Network.objects.filter(
                        ip_network=str(ip_network)).exists():
                    return Network.objects.create(
                        environment=environment,
                        name=name,
                        ip_network=ip_network,
                        has_pxe_server=has_pxe_server,
                        has_dhcp_server=has_dhcp_server,
                        forward=forward)
            except IntegrityError:
                transaction.rollback()

    def network_create(
        self, name, environment=None, ip_network=None, pool=None,
        has_dhcp_server=True, has_pxe_server=False,
        forward='nat'
    ):
        """Create network

        :rtype : Network
        """
        if ip_network:
            return Network.objects.create(
                environment=environment,
                name=name,
                ip_network=ip_network,
                has_pxe_server=has_pxe_server,
                has_dhcp_server=has_dhcp_server,
                forward=forward
            )
        return self._safe_create_network(
            environment=environment,
            forward=forward,
            has_dhcp_server=has_dhcp_server,
            has_pxe_server=has_pxe_server,
            name=name,
            pool=pool)

    def node_create(self, name, environment=None, role=None, vcpu=1,
                    memory=1024, has_vnc=True, metadata=None, hypervisor='kvm',
                    os_type='hvm', architecture='x86_64', boot=None):
        """Create node

        :rtype : Node
        """
        if not boot:
            boot = ['network', 'cdrom', 'hd']
        node = Node.objects.create(
            name=name, environment=environment,
            role=role, vcpu=vcpu, memory=memory,
            has_vnc=has_vnc, metadata=metadata, hypervisor=hypervisor,
            os_type=os_type, architecture=architecture, boot=json.dumps(boot)
        )
        return node

    def volume_get_predefined(self, uuid):
        """Get predefined volume

        :rtype : Volume
        """
        try:
            volume = Volume.objects.get(uuid=uuid)
        except Volume.DoesNotExist:
            volume = Volume(uuid=uuid)
        volume.fill_from_exist()
        volume.save()
        return volume

    def volume_create_child(self, name, backing_store, format=None,
                            environment=None):
        """Create new volume based on backing_store

        :rtype : Volume
        """
        return Volume.objects.create(
            name=name, environment=environment,
            capacity=backing_store.capacity,
            format=format or backing_store.format, backing_store=backing_store)

    def volume_create(self, name, capacity, format='qcow2', environment=None):
        """Create volume

        :rtype : Volume
        """
        return Volume.objects.create(
            name=name, environment=environment,
            capacity=capacity, format=format)

    def _generate_mac(self):
        """Generate MAC-address

        :rtype : String
        """
        return generate_mac()

    def interface_create(self, network, node, type='network',
                         mac_address=None, model='virtio',
                         interface_map={}):
        """Create interface

        :rtype : Interface
        """
        interfaces = []

        def _create(mac_addr=None):
            interface = Interface.objects.create(
                network=network, node=node, type=type,
                mac_address=mac_addr or self._generate_mac(), model=model)
            if type != 'bridge':
                interface.add_address(str(network.next_ip()))
            return interface

        if interface_map:
            if len(interface_map[network.name]) > 0:
                for iface in interface_map[network.name]:
                    interfaces.append(_create())
                return interfaces
        else:
            return _create(mac_address)

    def network_create_address(self, ip_address, interface):
        """Create address

        :rtype : Address
        """
        return Address.objects.create(ip_address=ip_address,
                                      interface=interface)

    def node_attach_volume(self, node, volume, device='disk', type='file',
                           bus='virtio', target_dev=None):
        """Attach volume to node

        :rtype : DiskDevice
        """
        return DiskDevice.objects.create(
            device=device, type=type, bus=bus,
            target_dev=target_dev or node.next_disk_name(),
            volume=volume, node=node)

    def synchronize_environments(self):
        Environment().synchronize_all()
