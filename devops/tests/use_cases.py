__author__ = 'alan'

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

