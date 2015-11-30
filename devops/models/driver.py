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

from devops.helpers import loader
from devops.models.base import BaseModel
from devops.models.base import ParamedModel


class Driver(ParamedModel, BaseModel):

    class Meta(object):
        db_table = 'devops_driver'
        app_label = 'devops'

    name = models.CharField(max_length=512)

    @staticmethod
    def driver_create(name, **params):
        DriverCls = loader.load_class(name)
        return DriverCls.objects.create(
            name=name, **params)

    def get_model_class(self, class_name, subtype=None):
        pass

    def get_allocated_networks(self):
        return []
