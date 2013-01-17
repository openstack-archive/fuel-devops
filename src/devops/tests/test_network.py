import unittest
from ipaddr import IPNetwork, IPv4Network
from devops.helpers.network import IpNetworksPool
from devops.models import Network, Address, Interface, Node


class TestIpNetworksPool(unittest.TestCase):

    def test_getting_subnetworks(self):
        pool = IpNetworksPool(networks=[IPNetwork('10.1.0.0/22')], prefix=24)
        self.assertTrue(IPv4Network('10.1.0.0/24') in pool)
        self.assertTrue(IPv4Network('10.1.1.0/24') in pool)
        self.assertTrue(IPv4Network('10.1.2.0/24') in pool)
        self.assertTrue(IPv4Network('10.1.3.0/24') in pool)

    def test_getting_ips(self):
        print IPv4Network('10.1.0.0/24')[-2]

    def test_network_iterator(self):
        network = Network.objects.create_network('internal', '10.1.0.0/24')
        node = Node.objects.create()
        interface = Interface.objects.create_interface(network=network, node=node)
        Address.objects.create_address(str('10.1.0.1'),interface=interface)
        ip = network.next_ip()
        Address.objects.create_address(str('10.1.0.3'),interface=interface)
        ip = network.next_ip()
        print ip

