from django.test import TestCase
from ipaddr import IPNetwork, IPv4Network
from devops.helpers.network import IpNetworksPool
from devops.manager import Manager


class TestIpNetworksPool(TestCase):

    manager = Manager()

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
        environment = self.manager.create_environment('test_env')
        node = self.manager.create_node('test_node')
        network = self.manager.create_network(
            environment=environment, name='internal', ip_network='10.1.0.0/24')
        interface = self.manager.create_interface(network=network, node=node)
        self.manager.create_address(str('10.1.0.1'),interface=interface)
        ip = network.next_ip()
        self.manager.create_address(str('10.1.0.3'),interface=interface)
        ip = network.next_ip()
        self.assertEquals('10.1.0.4', str(ip))

    def test_environment_values(self):
        environment = self.manager.create_environment('test_env')
        print environment.volumes

    def test_network_pool(self):
        environment = self.manager.create_environment('test_env')
        self.assertEqual('10.0.0.0/24', str(self.manager.create_network(
            environment=environment, name='internal', pool=None).ip_network))
        self.assertEqual('10.0.1.0/24', str(self.manager.create_network(
            environment=environment, name='external', pool=None).ip_network))
        self.assertEqual('10.0.2.0/24', str(self.manager.create_network(
            environment=environment, name='private', pool=None).ip_network))
        environment = self.manager.create_environment('test_env2')
        self.assertEqual('10.0.3.0/24', str(self.manager.create_network(
            environment=environment, name='internal', pool=None).ip_network))
        self.assertEqual('10.0.4.0/24', str(self.manager.create_network(
            environment=environment, name='external', pool=None).ip_network))
        self.assertEqual('10.0.5.0/24', str(self.manager.create_network(
            environment=environment, name='private', pool=None).ip_network))

    def test_node_creation(self):
        try:
            environment = self.manager.create_environment('test_env2')
            internal = self.manager.create_network(
                environment=environment, name='internal', pool=None)
#            external = self.manager.create_network(
#                environment=environment, name='external', pool=None)
#            private = self.manager.create_network(
#                environment=environment, name='private', pool=None)
            node = self.manager.create_node(name='test_node', environment=environment)
            self.manager.create_interface(node=node, network=internal)
#            self.manager.create_interface(node=node, network=external)
#            self.manager.create_interface(node=node, network=private)
            environment.define()
        except:
            environment.erase()




