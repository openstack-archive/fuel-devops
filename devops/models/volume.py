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

from devops.models.base import DriverModel


class Volume(DriverModel):
    class Meta:
        unique_together = ('name', 'environment')
        db_table = 'devops_volume'

    environment = models.ForeignKey('Environment', null=True)
    backing_store = models.ForeignKey('self', null=True)
    name = models.CharField(max_length=255, unique=False, null=False)
    uuid = models.CharField(max_length=255)
    capacity = models.BigIntegerField(null=False)
    format = models.CharField(max_length=255, null=False)

    def define(self):
        self.driver.volume_define(self)
        self.save()

    def erase(self):
        self.remove(verbose=False)

    def remove(self, verbose=False):
        if verbose or self.uuid:
            if verbose or self.driver.volume_exists(self):
                self.driver.volume_delete(self)
        self.delete()

    def get_capacity(self):
        return self.driver.volume_capacity(self)

    def get_format(self):
        return self.driver.volume_format(self)

    def get_path(self):
        return self.driver.volume_path(self)

    def fill_from_exist(self):
        self.capacity = self.get_capacity()
        self.format = self.get_format()

    def upload(self, path):
        self.driver.volume_upload(self, path)

    @classmethod
    def volume_get_predefined(cls, uuid):
        """Get predefined volume

        :rtype : Volume
        """
        try:
            volume = cls.objects.get(uuid=uuid)
        except cls.DoesNotExist:
            volume = cls(uuid=uuid)
        volume.fill_from_exist()
        volume.save()
        return volume

    @classmethod
    def volume_create_child(cls, name, backing_store, format=None,
                            environment=None):
        """Create new volume based on backing_store

        :rtype : Volume
        """
        return cls.objects.create(
            name=name, environment=environment,
            capacity=backing_store.capacity,
            format=format or backing_store.format, backing_store=backing_store)

    @classmethod
    def volume_create(cls, name, capacity, format='qcow2', environment=None):
        """Create volume

        :rtype : Volume
        """
        return cls.objects.create(
            name=name, environment=environment,
            capacity=capacity, format=format)
