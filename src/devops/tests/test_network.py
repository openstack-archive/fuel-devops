import unittest
from ipaddr import IPNetwork
from devops.helpers.network import IpNetworksPool


class TestIpNetworksPool(unittest.TestCase):
    def test_getting_subnetworks(self):
        pool = IpNetworksPool(networks=[IPNetwork('10.1.0.0/22')], prefix=24)

        for net in pool.get([]):
            print net

        print pool.get([]).next()


#        self.assertTrue(IPv4Network('10.1.0.0/24') in nets)
#        self.assertTrue(IPv4Network('10.1.1.0/24') in nets)
#        self.assertTrue(IPv4Network('10.1.2.0/24') in nets)
#        self.assertTrue(IPv4Network('10.1.3.0/24') in nets)

