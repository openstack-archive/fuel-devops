from src.devops.helpers.network import IpNetworksPool
from src.devops.error import DevopsError

import logging

logger = logging.getLogger(__name__)


class Controller:

    def define_networks(self):
        networks_pool = IpNetworksPool()
        for network in environment.networks:
            network.ip_addresses = self.networks_pool.get()

            #            if network.pxe:
            #                network.dhcp_server = True
            #                network.tftp_path

            if network.dhcp_server or network.reserve_static:
                allocated_addresses = []
                for interface in network.interfaces:
                    for address in interface.ip_addresses:
                        if address in network.ip_addresses:
                            allocated_addresses.append(address)
                dhcp_allowed_addresses = list(network.ip_addresses)[2:-2]
                for interface in network.interfaces:
                    logger.info("Enumerated interfaces '%s' '%s'" % (interface.node, interface.network.name))
                    logger.info(list(interface.ip_addresses))
                    if not len(list(interface.ip_addresses)):
                        address = self.get_first_free_address(
                            dhcp_allowed_addresses,
                            allocated_addresses)
                        interface.ip_addresses.append(address)
                        allocated_addresses.append(address)

    def build_environment(self, environment):

        for network in environment.networks:
            self.driver.create_network(network)
            network.start()

        for node in environment.nodes:
            self._build_node(node)
            node.driver = self.driver

    def destroy_environment(self, environment):
        for node in environment.nodes:
            self.driver.stop_node(node)
            for snapshot in node.snapshots:
                self.driver.delete_snapshot(node, snapshot)
            for disk in node.disks:
                self.driver.delete_disk(disk)
            self.driver.delete_node(node)

        for network in environment.networks:
            self.driver.delete_network(network)

    def _build_node(self, node):
        for disk in filter(lambda d: d.path is None, node.disks):
            logger.debug("Creating disk file for node '%s'" % node.name)
            disk.path = self.driver.create_disk(disk)

        logger.debug("Creating node '%s'" % node.name)
        self.driver.create_node(node)

    def get_first_free_address(self, allowed_addresses, allocated_addresses):
        s = set(allocated_addresses)
        for x in allowed_addresses:
            if x not in s:
                return x
        raise DevopsError("Free address not found")
