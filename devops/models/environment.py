#    Copyright 2013 - 2015 Mirantis, Inc.
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

from django.db import models

from devops import logger
from devops.models.base import DriverModel


class Environment(DriverModel):
    class Meta:
        db_table = 'devops_environment'

    name = models.CharField(max_length=255, unique=True, null=False)

    # Syntactic sugar.

    def volume(self, *args, **kwargs):
        return self.volume_set.get(*args, **kwargs)

    def volumes(self, *args, **kwargs):
        return self.volume_set.filter(*args, **kwargs)

    def network(self, *args, **kwargs):
        return self.network_set.get(*args, **kwargs)

    def networks(self, *args, **kwargs):
        return self.network_set.filter(*args, **kwargs)

    def node(self, *args, **kwargs):
        return self.node_set.get(*args, **kwargs)

    def nodes(self, *args, **kwargs):
        return self.node_set.filter(*args, **kwargs)

    @classmethod
    def create(cls, name):
        """Create Environment instance with given name.

        :rtype: devops.models.Environment
        """
        return cls.objects.create(name=name)

    @classmethod
    def get(cls, *args, **kwargs):
        return cls.objects.get(*args, **kwargs)

    @classmethod
    def list(cls):
        return cls.objects.all()

    # End of syntactic sugar.

    def has_snapshot(self, name):
        return all(map(lambda x: x.has_snapshot(name), self.nodes()))

    def define(self):
        for network in self.networks():
            network.define()
        for volume in self.volumes():
            volume.define()
        for node in self.nodes():
            node.define()

    def start(self, nodes=None):
        for network in self.networks():
            network.start()
        for node in nodes or self.nodes():
            node.start()

    def destroy(self, verbose=False):
        for node in self.nodes():
            node.destroy(verbose=verbose)

    def erase(self):
        for node in self.nodes():
            node.erase()
        for network in self.networks():
            network.erase()
        for volume in self.volumes():
            volume.erase()
        self.delete()

    @classmethod
    def erase_empty(cls):
        for env in cls.objects.all():
            if len(env.nodes()) == 0:
                env.delete()

    def suspend(self, verbose=False):
        for node in self.nodes():
            node.suspend(verbose)

    def resume(self, verbose=False):
        for node in self.nodes():
            node.resume(verbose)

    def snapshot(self, name=None, description=None, force=False):
        for node in self.nodes():
            node.snapshot(name=name, description=description, force=force)

    def revert(self, name=None, destroy=True, flag=True):
        if destroy:
            for node in self.nodes():
                node.destroy(verbose=False)
        if (flag and
                not all([node.has_snapshot(name) for node in self.nodes()])):
            raise Exception("some nodes miss snapshot,"
                            " test should be interrupted")
        for node in self.nodes():
            node.revert(name, destroy=False)

    @classmethod
    def synchronize_all(cls):
        driver = cls.get_driver()
        nodes = {driver._get_name(e.name, n.name): n
                 for e in cls.objects.all()
                 for n in e.nodes()}
        domains = set(driver.node_list())

        # FIXME (AWoodward) This willy nilly wacks domains when you run this
        #  on domains that are outside the scope of devops, if anything this
        #  should cause domains to be imported into db instead of undefined.
        #  It also leaves network and volumes around too
        #  Disabled untill a safer implmentation arrives

        # Undefine domains without devops nodes
        #
        # domains_to_undefine = domains - set(nodes.keys())
        # for d in domains_to_undefine:
        #    driver.node_undefine_by_name(d)

        # Remove devops nodes without domains
        nodes_to_remove = set(nodes.keys()) - domains
        for n in nodes_to_remove:
            nodes[n].delete()
        cls.erase_empty()

        logger.info('Undefined domains: %s, removed nodes: %s' %
                    (0, len(nodes_to_remove)))
