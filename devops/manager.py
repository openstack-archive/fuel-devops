import json
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "devops.settings")
from django.db import IntegrityError, transaction
import ipaddr
from devops.helpers.helpers import generate_mac
from devops.helpers.network import IpNetworksPool
from devops.models import Address, Interface, Node, Network, Environment, \
    Volume, DiskDevice, ExternalModel


class Manager(object):
    def __init__(self):
        super(Manager, self).__init__()
        self.default_pool = None

    def environment_create(self, name):
        """
        :rtype : Environment
        """
        return Environment.objects.create(name=name)

    def environment_list(self):
        return Environment.objects.all()

    def environment_get(self, name):
        """
        :rtype : Environment
        """
        return Environment.objects.get(name=name)

    def create_network_pool(self, networks, prefix):
        """
        :rtype : IpNetworksPool
        """
        pool = IpNetworksPool(networks=networks, prefix=prefix)
        pool.set_allocated_networks(ExternalModel.get_allocated_networks())
        return pool

    def _get_default_pool(self):
        """
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
                if not Network.objects.filter(ip_network=str(ip_network)).exists():
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
        """
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
        """
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
        """
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
        """
        :rtype : Volume
        """
        return Volume.objects.create(
            name=name, environment=environment,
            capacity=backing_store.capacity,
            format=format or backing_store.format, backing_store=backing_store)

    def volume_create(self, name, capacity, format='qcow2', environment=None):
        """
        :rtype : Volume
        """
        return Volume.objects.create(
            name=name, environment=environment,
            capacity=capacity, format=format)

    def _generate_mac(self):
        """
        :rtype : String
        """
        return generate_mac()

    def interface_create(self, network, node, type='network',
                         mac_address=None, model='virtio'):
        """
        :rtype : Interface
        """
        interface = Interface.objects.create(
            network=network, node=node, type=type,
            mac_address=mac_address or self._generate_mac(), model=model)
        interface.add_address(str(network.next_ip()))
        return interface

    def network_create_address(self, ip_address, interface):
        """
        :rtype : Address
        """
        return Address.objects.create(ip_address=ip_address,
                                      interface=interface)

    def node_attach_volume(self, node, volume, device='disk', type='file',
                           bus='virtio', target_dev=None):
        """
        :rtype : DiskDevice
        """
        return DiskDevice.objects.create(
            device=device, type=type, bus=bus,
            target_dev=target_dev or node.next_disk_name(),
            volume=volume, node=node)
