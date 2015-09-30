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

import mock
import pytest

from devops.tests import factories


@pytest.fixture(scope="session", autouse=True)
def mock_libvirt(request):
    """Mock libvirt connection"""
    libvirt_patcher = mock.patch('libvirt.open')
    libvirt_mock = libvirt_patcher.start()

    def fin():
        libvirt_patcher.stop()

    request.addfinalizer(fin)

    return libvirt_mock


@pytest.fixture(scope="session", autouse=True)
def mock_node_timeout(request):
    """Mock all 'wait' methods used for nodes"""
    wait_patcher = mock.patch('devops.helpers.node_manager.wait')
    _wait_patcher = mock.patch('devops.models.node._wait')
    wait_patcher.start()
    _wait_patcher.start()

    def fin():
        wait_patcher.stop()
        _wait_patcher.stop()

    request.addfinalizer(fin)


@pytest.fixture
def single_admin_node():
    """Create single environment with one admin node"""
    factories.SingleAddressFactory(
        interface__node__name='admin',
        interface__network__name='admin')
