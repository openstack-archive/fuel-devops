import ipaddr

class IpNetworksPool:
    def __init__(self, networks=None, prefix=24, allocated_networks=None):
        if allocated_networks is None:
            allocated_networks = []
        if networks is None:
            networks = [ipaddr.IPNetwork('10.0.0.0/16')]
        self._sub_nets = self._initialize(networks, prefix, allocated_networks)

    def _overlaps(self, network, allocated_networks):
        return any(an.overlaps(network) for an in allocated_networks)

    def _initialize(self, networks, prefix, allocated_networks):
        for network in networks:
            for sub_net in network.iter_subnets(new_prefix=prefix):
                if not self._overlaps(sub_net, allocated_networks):
                    yield sub_net

    def __iter__(self):
        self._sub_nets.next()

