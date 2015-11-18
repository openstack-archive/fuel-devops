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


@factory.use_strategy(factory.BUILD_STRATEGY)
class EnvironmentFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = models.Environment

    name = fuzzy.FuzzyText('test_env_')


@factory.use_strategy(factory.BUILD_STRATEGY)
class VolumeFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = models.Volume

    environment = factory.SubFactory(EnvironmentFactory)
    backing_store = factory.SubFactory('devops.tests.factories.VolumeFactory',
                                       backing_store=None)
    name = fuzzy.FuzzyText('test_volume_')
    uuid = FuzzyUuid()
    capacity = fuzzy.FuzzyInteger(50, 100)
    format = fuzzy.FuzzyText('qcow2_')


def fuzzy_string(*args, **kwargs):
    """Shortcut for getting fuzzy text"""
    return fuzzy.FuzzyText(*args, **kwargs).fuzz()
