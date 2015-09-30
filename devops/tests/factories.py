# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

import uuid

import factory
from factory import fuzzy

from devops import models


class FuzzyUuid(fuzzy.BaseFuzzyAttribute):

    def fuzz(self):
        return str(uuid.uuid4())


class EnvironmentFactory(factory.django.DjangoModelFactory):
    """Create Environment with randomized name."""
    class Meta:
        model = models.Environment
        django_get_or_create = ('name',)

    name = fuzzy.FuzzyText('test_env_')


class SingleEnvironmentFactory(EnvironmentFactory):
    """Create Environment with 'test_env' name, without randomization."""
    name = 'test_env'


@factory.use_strategy(factory.BUILD_STRATEGY)
class VolumeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Volume

    environment = factory.SubFactory(EnvironmentFactory)
    backing_store = factory.SubFactory('devops.tests.factories.VolumeFactory',
                                       backing_store=None)
    name = fuzzy.FuzzyText('test_volume_')
    uuid = FuzzyUuid()
    capacity = fuzzy.FuzzyInteger(50, 100)
    format = fuzzy.FuzzyText('qcow2_')


class NodeFactory(factory.django.DjangoModelFactory):
    """Create Node with Enviroment having randomized name."""
    class Meta:
        model = models.Node

    environment = factory.SubFactory(EnvironmentFactory)


class SingleNodeFactory(NodeFactory):
    """Create Node with Environment having 'test_env' name."""
    environment = factory.SubFactory(SingleEnvironmentFactory)


class NetworkFactory(factory.django.DjangoModelFactory):
    """Create Network with Environment having randomized name."""
    class Meta:
        model = models.Network

    environment = factory.SubFactory(EnvironmentFactory)
    ip_network = '10.21.0.0/24'
    has_dhcp_server = False
    has_pxe_server = False


class SingleNetworkFactory(NetworkFactory):
    """Create Network with Environment having 'test_env' name."""
    environment = factory.SubFactory(SingleEnvironmentFactory)


class InterfaceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Interface

    node = factory.SubFactory(NodeFactory)
    network = factory.SubFactory(NetworkFactory)


class SingleInterfaceFactory(InterfaceFactory):
    node = factory.SubFactory(SingleNodeFactory)
    network = factory.SubFactory(SingleNetworkFactory)


class AddressFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Address

    interface = factory.SubFactory(InterfaceFactory)
    ip_address = '10.21.0.2'


class SingleAddressFactory(AddressFactory):
    interface = factory.SubFactory(SingleInterfaceFactory)


def fuzzy_string(*args, **kwargs):
    """Shortcut for getting fuzzy text"""
    return fuzzy.FuzzyText(*args, **kwargs).fuzz()
