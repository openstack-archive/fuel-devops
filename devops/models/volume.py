#    Copyright 2013 - 2016 Mirantis, Inc.
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

from devops.models.base import BaseModel
from devops.models.base import ParamedModel
from devops.models.base import ParamField


class Volume(ParamedModel, BaseModel):
    class Meta(object):
        unique_together = (('name', 'node'), ('name', 'group'))
        db_table = 'devops_volume'
        app_label = 'devops'

    backing_store = models.ForeignKey('self', null=True)
    name = models.CharField(max_length=255, unique=False, null=False)
    node = models.ForeignKey('Node', null=True)
    group = models.ForeignKey('Group', null=True)

    @property
    def driver(self):
        return self.node.driver if self.node else self.group.driver

    def define(self, *args, **kwargs):
        self.save()

    def erase(self, *args, **kwargs):
        self.remove()

    def remove(self, *args, **kwargs):
        self.delete()


class DiskDevice(ParamedModel):
    class Meta(object):
        db_table = 'devops_diskdevice'
        app_label = 'devops'

    node = models.ForeignKey('Node', null=False)
    volume = models.ForeignKey('Volume', null=True)

    # TODO(astudenov): temporarily added for ipmi driver
    # and driverless testcase. These fields should be removed
    # after refactoring of volume section in themplate
    device = ParamField()
    type = ParamField()
    bus = ParamField()
    target_dev = ParamField()
