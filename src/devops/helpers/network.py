import ipaddr

class IpNetworksPool:
    def __init__(self, networks=None, prefix=24):
        if networks is None:
            networks = [ipaddr.IPNetwork('10.0.0.0/16')]
        self.networks = networks
        self.prefix = prefix

    def overlaps(self, network, allocated_networks):
        for allocated_network in allocated_networks:
            if allocated_network.overlaps(network):
                return True
        return False

    def get(self, allocated_networks):
        for network in self.networks:
            for sub_net in network.iter_subnets:
                if not self.overlaps(sub_net, allocated_networks):
                    yield sub_net

