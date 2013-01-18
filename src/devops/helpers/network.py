class IpNetworksPool(object):
    def __init__(self, networks, prefix):
        self.networks = networks
        self.prefix = prefix
        self.allocated_networks=[]
        self._initialize_generator()

    def set_allocated_networks(self, allocated_networks):
        self.allocated_networks=allocated_networks
        self._initialize_generator()

    def _overlaps(self, network, allocated_networks):
        return any(an.overlaps(network) for an in allocated_networks)

    def _initialize_generator(self):
        def _get_generator():
            for network in self.networks:
                for sub_net in network.iter_subnets(new_prefix=self.prefix):
                    if not self._overlaps(sub_net, self.allocated_networks):
                        yield sub_net
        self._generator = _get_generator()

    def __iter__(self):
        return self._generator

    def next(self):
        return self._generator.next()

