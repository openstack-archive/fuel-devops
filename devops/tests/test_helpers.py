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

import time
import unittest

import devops.error
from devops.helpers import helpers


class TestSnaphotList(unittest.TestCase):

    def test_get_keys(self):
        keys = helpers.get_keys(
            'IP',
            'NETMASK',
            'GW',
            'HOSTNAME',
            'NAT_INTERFACE',
            'DNS1',
            'SHOWMENU',
            'BUILD_IMAGES'
        )

        self.assertIn('<Wait>\n<Esc>\n<Wait>\n', keys)
        self.assertIn('ip=IP::GW:NETMASK:HOSTNAME:enp0s3:none', keys)
        self.assertIn('netmask=NETMASK', keys)
        self.assertIn('gw=GW', keys)
        self.assertIn('dns1=DNS1', keys)
        self.assertIn('nameserver=DNS1', keys)
        self.assertIn('hostname=HOSTNAME', keys)
        self.assertIn('dhcp_interface=NAT_INTERFACE', keys)
        self.assertIn('showmenu=SHOWMENU', keys)
        self.assertIn('build_images=BUILD_IMAGES', keys)

    def test_get_keys_centos6(self):
        keys = helpers.get_keys(
            ip='IP',
            mask='NETMASK',
            gw='GW',
            hostname='HOSTNAME',
            nat_interface='NAT_INTERFACE',
            dns1='DNS1',
            showmenu='SHOWMENU',
            build_images='BUILD_IMAGES',
            centos_version=6
        )

        self.assertIn('<Wait>\n<Esc>\n<Wait>\n', keys)
        self.assertIn('ip=IP', keys)
        self.assertIn('netmask=NETMASK', keys)
        self.assertIn('gw=GW', keys)
        self.assertIn('dns1=DNS1', keys)
        self.assertIn('nameserver=DNS1', keys)
        self.assertIn('hostname=HOSTNAME', keys)
        self.assertIn('dhcp_interface=NAT_INTERFACE', keys)
        self.assertIn('showmenu=SHOWMENU', keys)
        self.assertIn('build_images=BUILD_IMAGES', keys)

    def test_wait(self):

        self.external_storage = None

        def dummy_method(to_sleep, *args, **kwargs):
            time.sleep(to_sleep)
            item = self.external_storage.pop(0)
            try:
                if issubclass(item, Exception):
                    raise item("message")
            except TypeError:
                return item

        self.external_storage = [False, False, True]
        self.assertTrue(
            helpers.wait(dummy_method, interval=1, timeout=9,
                         predicate_kwargs={'to_sleep': 2}))

        self.external_storage = [False, False, True]
        self.assertRaises(devops.error.TimeoutError,
                          helpers.wait, dummy_method, interval=1, timeout=8,
                          predicate_args=(5, "qwerty", 123456,),
                          predicate_kwargs={'another_arg': -1})

        self.external_storage = [devops.error.DevopsEnvironmentError,
                                 devops.error.DevopsEnvironmentError,
                                 'useful_result']
        self.assertEqual(
            'useful_result',
            helpers.wait_pass(
                dummy_method, interval=1, timeout=6,
                predicate_kwargs={'to_sleep': 1},
                expected=devops.error.DevopsEnvironmentError))

        self.external_storage = [devops.error.DevopsEnvironmentError,
                                 devops.error.DevopsEnvironmentError,
                                 'result']
        self.assertRaises(devops.error.TimeoutError,
                          helpers.wait_pass, dummy_method,
                          interval=1, timeout=8,
                          predicate_kwargs={'to_sleep': 5},
                          expected=devops.error.DevopsEnvironmentError)

        self.external_storage = [devops.error.DevopsEnvironmentError,
                                 devops.error.AuthenticationError]

        self.assertRaises(devops.error.AuthenticationError,
                          helpers.wait_pass, dummy_method,
                          interval=1, timeout=8,
                          predicate_kwargs={'to_sleep': 1},
                          expected=devops.error.DevopsEnvironmentError)

        self.external_storage = [devops.error.DevopsEnvironmentError,
                                 devops.error.DevopsCalledProcessError,
                                 True]

        self.assertTrue(
            helpers.wait_pass(
                dummy_method, interval=1, timeout=5,
                predicate_kwargs={'to_sleep': 1},
                expected=(
                    devops.error.DevopsEnvironmentError,
                    devops.error.DevopsCalledProcessError)))
