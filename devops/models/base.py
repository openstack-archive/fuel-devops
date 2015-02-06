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

from django.conf import settings
from django.db import models
from django.utils.importlib import import_module
from datetime import datetime


def choices(*args, **kwargs):
    defaults = {'max_length': 255, 'null': False}
    defaults.update(kwargs)
    defaults.update(choices=double_tuple(*args))
    return models.CharField(**defaults)


def double_tuple(*args):
    dict = []
    for arg in args:
        dict.append((arg, arg))
    return tuple(dict)


class DriverModel(models.Model):
    _driver = None
    created = models.DateTimeField(auto_now_add=True, default=datetime.now())

    class Meta:
        abstract = True

    @classmethod
    def get_driver(cls):
        """Get driver

        :rtype : DevopsDriver
        """
        driver = import_module(settings.DRIVER)
        cls._driver = cls._driver or driver.DevopsDriver(
            **settings.DRIVER_PARAMETERS)
        return cls._driver

    @property
    def driver(self):
        """Driver object

        :rtype : DevopsDriver
        """
        return self.get_driver()

    def get_creation_date(self):
        return self.created
