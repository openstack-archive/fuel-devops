#    Copyright 2014 Mirantis, Inc.
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

import os
import unittest
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "devops.settings")
from devops import manager
from devops.driver.libvirt import libvirt_driver
from devops.helpers.helpers import _get_file_size


class UseCases(unittest.TestCase):
    driver = libvirt_driver.DevopsDriver()
    manager = manager.Manager()

    def test_volumes_for_pptesting(self):
        images_for_upload = {
            "ubuntu-12.04.3-desktop-amd64.iso":
                "/tmp/ubuntu-12.04.3-desktop-amd64.iso",
            "centos6.4-base.qcow2":
                "/tmp/centos6.4-base.qcow2",
            }

        for name, vol in images_for_upload.iteritems():
            v = self.manager.volume_create(name,
                                           _get_file_size(vol))
            if not self.driver.volume_exists(v):
                self.driver.volume_define(v)
                self.driver.volume_upload(v, vol)

