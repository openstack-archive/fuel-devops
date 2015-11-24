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

from devops.models.base import BaseModel
from devops.models.base import ParamedModel
from devops.models.base import choices


class Volume(ParamedModel, BaseModel):
    class Meta(object):
        unique_together = ('name', 'group')
        db_table = 'devops_volume'
        app_label = 'devops'

    group = models.ForeignKey('Group', null=True)
    backing_store = models.ForeignKey('self', null=True)
    name = models.CharField(max_length=255, unique=False, null=False)

    @property
    def driver(self):
        self.group.driver

    def define(self):
        pass

    def erase(self):
        pass

    # TO REWRITE
    @classmethod
    def volume_get_predefined(cls, uuid):
        """Get predefined volume

        :rtype : Volume
        """
        try:
            # TODO: cant filter by uuid
            volume = cls.objects.get(uuid=uuid)
        except cls.DoesNotExist:
            volume = cls(uuid=uuid)
        volume.fill_from_exist()
        volume.save()
        return volume

    @classmethod
    def volume_create_child(cls, name, backing_store, format=None,
                            group=None):
        """Create new volume based on backing_store

        :rtype : Volume
        """
        return cls.objects.create(
            name=name, group=group,
            capacity=backing_store.capacity,
            format=format or backing_store.format, backing_store=backing_store)

    # @classmethod
    # def volume_create(cls, name, capacity, format='qcow2', group=None):
    #     """Create volume

    #     :rtype : Volume
    #     """
    #     return cls.objects.create(
    #         name=name, group=group,
    #         capacity=capacity, format=format)


class DiskDevice(models.Model):
    class Meta:
        db_table = 'devops_diskdevice'
        app_label = 'devops'

    node = models.ForeignKey('Node', null=False)
    volume = models.ForeignKey('Volume', null=True)
    device = choices('disk', 'cdrom')
    type = choices('file')
    bus = choices('virtio')
    target_dev = models.CharField(max_length=255, null=False)

    @classmethod
    def node_attach_volume(cls, node, volume, device='disk', type='file',
                           bus='virtio', target_dev=None):
        """Attach volume to node

        :rtype : DiskDevice
        """
        return cls.objects.create(
            device=device, type=type, bus=bus,
            target_dev=target_dev or node.next_disk_name(),
            volume=volume, node=node)
