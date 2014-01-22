__author__ = 'alan'

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "devops.settings")
from devops.manager import Manager
from devops.helpers.helpers import _get_file_size
from devops.driver.libvirt.libvirt_driver import DevopsDriver
import unittest


class UseCases(unittest.TestCase):
    driver = DevopsDriver()
    manager = Manager()

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

