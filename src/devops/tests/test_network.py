import unittest
from ipaddr import IPNetwork, IPv4Network
from devops.helpers.network import IpNetworksPool
from devops.models import Network, Address, Interface, Node, Environment


class TestIpNetworksPool(unittest.TestCase):

    def test_getting_subnetworks(self):
        pool = IpNetworksPool(networks=[IPNetwork('10.1.0.0/22')], prefix=24)
        pool.set_allocated_networks([IPv4Network('10.1.1.0/24')])
        networks  = list(pool)
        self.assertTrue(IPv4Network('10.1.0.0/24') in networks)
        self.assertFalse(IPv4Network('10.1.1.0/24') in networks)
        self.assertTrue(IPv4Network('10.1.2.0/24') in networks)
        self.assertTrue(IPv4Network('10.1.3.0/24') in networks)

    def test_getting_ips(self):
        self.assertEquals('10.1.0.254', str(IPv4Network('10.1.0.0/24')[-2]))

    def test_network_iterator(self):
        environment = Environment.objects.create_environment('test_env')
        network = Network.objects.create_network(
            environment=environment, name='internal', ip_network='10.1.0.0/24')
        node = Node.objects.create()
        interface = Interface.objects.create_interface(network=network, node=node)
        Address.objects.create_address(str('10.1.0.1'),interface=interface)
        ip = network.next_ip()
        Address.objects.create_address(str('10.1.0.3'),interface=interface)
        ip = network.next_ip()
        self.assertEquals('10.1.0.4', str(ip))

    def test_network_pool(self):
        environment = Environment.objects.create_environment('test_env')
        self.assertEqual('10.0.0.0/24', str(Network.objects.create_network(
            environment=environment, name='internal', pool=None).ip_network))
        self.assertEqual('10.0.1.0/24', str(Network.objects.create_network(
            environment=environment, name='external', pool=None).ip_network))
        self.assertEqual('10.0.2.0/24', str(Network.objects.create_network(
            environment=environment, name='private', pool=None).ip_network))
        environment = Environment.objects.create_environment('test_env2')
        self.assertEqual('10.0.3.0/24', str(Network.objects.create_network(
            environment=environment, name='internal', pool=None).ip_network))
        self.assertEqual('10.0.4.0/24', str(Network.objects.create_network(
            environment=environment, name='external', pool=None).ip_network))
        self.assertEqual('10.0.5.0/24', str(Network.objects.create_network(
            environment=environment, name='private', pool=None).ip_network))

    def test_node_creation(self):
        environment = Environment.objects.create_environment('test_env')
        Network.objects.create_network(
            environment=environment, name='internal', pool=None)
        Network.objects.create_network(
            environment=environment, name='external', pool=None)
        Network.objects.create_network(
            environment=environment, name='private', pool=None)
        environment = Environment.objects.create_environment('test_env2')
        Network.objects.create_network(
            environment=environment, name='internal', pool=None)
        Network.objects.create_network(
            environment=environment, name='external', pool=None)
        Network.objects.create_network(
            environment=environment, name='private', pool=None)
        node = Node.objects.create_node('test_node')
        node.define()
