#    Copyright 2013 - 2014 Mirantis, Inc.
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

class DevopsDriverBase(object):

    # Node core functions
    def node_list(self):
        pass

    def node_create(self):
        pass

    def node_delete(self):
        pass

    def node_start(self):
        pass

    def node_suspend(self):
        pass

    def node_resume(self):
        pass

    def node_stop(self):
        pass

    # Network core functions
    def network_list(self):
        pass

    def network_create(self):
        pass

    def network_delete(self):
        pass

    def network_start(self):
        pass

    def network_stop(self):
        pass

    # Snapshot functions
    def snapshot_list(self):
        pass

    def snapshot_create(self):
        pass

    def snapshot_delete(self):
        pass

    def snapshot_revert(self):
        pass

    # IP functions
    def get_allocated_networks(self):
        pass