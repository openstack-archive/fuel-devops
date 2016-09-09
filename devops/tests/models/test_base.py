#    Copyright 2016 Mirantis, Inc.
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

# pylint: disable=no-self-use

from django.test import TestCase

from devops import error
from devops import models
from devops.models import base


class MyModel(models.Driver):

    field = base.ParamField(default=10)
    number = base.ParamField(default=None, choices=(None, 'one', 'two'))
    multi = base.ParamMultiField(
        sub1=base.ParamField(default='abc'),
        sub2=base.ParamField(default=15, choices=(11, 13, 15)),
    )


class TestParamedModel(TestCase):

    def test_default(self):
        t = MyModel(name='test_driver_model')
        assert t.field == 10
        assert t.number is None
        assert t.multi.sub1 == 'abc'
        assert t.multi.sub2 == 15

        t.save()
        assert t.field == 10
        assert t.number is None
        assert t.multi.sub1 == 'abc'
        assert t.multi.sub2 == 15

        assert t.params == {
            '_class': 'devops.tests.models.test_base:MyModel',
            'field': 10,
            'multi': {
                'sub2': 15,
                'sub1': 'abc'
            },
            'number': None,
        }

        t2 = models.Driver.objects.get(name='test_driver_model')
        assert isinstance(t2, MyModel)
        assert t2.field == 10
        assert t2.number is None
        assert t2.multi.sub1 == 'abc'
        assert t2.multi.sub2 == 15

        assert t2.params == {
            '_class': 'devops.tests.models.test_base:MyModel',
            'field': 10,
            'multi': {
                'sub2': 15,
                'sub1': 'abc'
            },
            'number': None,
        }

    def test_values(self):
        t = MyModel(number='one', multi=dict(sub2=13))
        t.save()

        assert t.field == 10
        assert t.number == 'one'
        assert t.multi.sub1 == 'abc'
        assert t.multi.sub2 == 13
        assert t.params == {
            '_class': 'devops.tests.models.test_base:MyModel',
            'field': 10,
            'multi': {
                'sub2': 13,
                'sub1': 'abc'
            },
            'number': 'one',
        }

    def test_assigment(self):
        t = MyModel()
        t.save()

        t.field = 50
        t.number = 'two'
        t.multi.sub1 = 'aaa'
        t.multi.sub2 = 11

        assert t.field == 50
        assert t.number == 'two'
        assert t.multi.sub1 == 'aaa'
        assert t.multi.sub2 == 11
        assert t.params == {
            '_class': 'devops.tests.models.test_base:MyModel',
            'field': 50,
            'multi': {
                'sub2': 11,
                'sub1': 'aaa'
            },
            'number': 'two',
        }

    def test_unknown_field(self):
        with self.assertRaises(TypeError):
            MyModel(unknown=0)
        with self.assertRaises(error.DevopsException):
            MyModel(multi=dict(unknown='aaa'))
        with self.assertRaises(error.DevopsException):
            MyModel(multi='aaa')

    def test_not_in_choices(self):
        with self.assertRaises(error.DevopsException):
            MyModel(number=0)
        with self.assertRaises(error.DevopsException):
            t = MyModel()
            t.number = 0
        with self.assertRaises(error.DevopsException):
            MyModel(multi=dict(sub2='aaa'))
        with self.assertRaises(error.DevopsException):
            t = MyModel()
            t.multi.sub2 = 'aaa'

    def test_filter(self):
        t = MyModel(name='t1', field=0, multi=dict(sub1='aaa'))
        t.save()
        t2 = MyModel(name='t2', field=0)
        t2.save()
        t3 = MyModel(name='t3', field=5, multi=dict(sub1='bbb'))
        t3.save()
        t4 = MyModel(name='t4', field=5)
        t4.save()

        o = MyModel.objects
        assert len(o.filter(multi__sub2=15)) == 4
        assert len(o.filter(field=0)) == 2
        assert len(o.filter(field=0)) == 2
        assert len(o.filter(name='t3', field=0)) == 0
        assert len(o.filter(name='t1', field=0)) == 1
        assert len(o.filter(name='t2', field=0)) == 1
        assert o.get(name='t2', field=0).id == t2.id
        assert o.get(name='t2', multi__sub1='abc').id == t2.id

    def test_related_queryset(self):
        d = models.Driver(name='devops.driver.libvirt')
        d.save()
        g = models.Group(name='test', driver=d)
        g.save()
        g.add_node(name='n1', role='fuel_slave', hypervisor='test', uuid='abc')
        g.add_node(name='n2', role='fuel_slave', hypervisor='test', uuid='bcd')
        g.add_node(name='n3', role='fuel_slave', hypervisor='kvm', uuid='cde')
        g.add_node(name='n4', role='fuel_slave', hypervisor='kvm', uuid='def')

        assert len(g.node_set.all()) == 4
        assert len(g.node_set.filter(role='fuel_slave')) == 4
        assert len(g.node_set.filter(hypervisor='test')) == 2
        assert len(g.node_set.filter(name='n1', hypervisor='test')) == 1
        assert len(g.node_set.filter(uuid='def', hypervisor='kvm')) == 1
        assert len(g.node_set.filter(name='n2', role='fuel_slave',
                                     hypervisor='test', uuid='bcd')) == 1
        assert len(g.node_set.filter(name='n1', hypervisor='kvm')) == 0
        assert len(g.node_set.filter(hypervisor='kvm', uuid='qqq')) == 0

        assert g.node_set.get(name='n1').uuid == 'abc'
        assert g.node_set.get(uuid='abc').name == 'n1'
        assert g.node_set.get(role='fuel_slave', uuid='cde').name == 'n3'
        assert g.node_set.get(hypervisor='kvm', name='n4').uuid == 'def'
        with self.assertRaises(models.Node.DoesNotExist):
            g.node_set.get(hypervisor='kvm', uuid='bcd')
        with self.assertRaises(models.Node.DoesNotExist):
            g.node_set.get(role='qqq', hypervisor='kvm')


class MyMultiModel(models.Driver):

    multi = base.ParamMultiField(
        sub1=base.ParamField(default='abc'),
        multi2=base.ParamMultiField(
            sub2=base.ParamField(default=13),
        )
    )


class TestMultiField(TestCase):

    def test_default(self):
        t = MyMultiModel()
        assert t.multi.sub1 == 'abc'
        assert t.multi.multi2.sub2 == 13
        t.save()
        assert t.params == {
            '_class': 'devops.tests.models.test_base:MyMultiModel',
            'multi': {
                'sub1': 'abc',
                'multi2': {'sub2': 13}
            }
        }
        assert t.multi.sub1 == 'abc'
        assert t.multi.multi2.sub2 == 13

    def test_values(self):
        t = MyMultiModel(multi=dict(sub1='def', multi2=dict(sub2=50)))
        t.save()
        assert t.multi.sub1 == 'def'
        assert t.multi.multi2.sub2 == 50
        assert t.params == {
            '_class': 'devops.tests.models.test_base:MyMultiModel',
            'multi': {
                'sub1': 'def',
                'multi2': {'sub2': 50}
            }
        }

    def test_assigment(self):
        t = MyMultiModel()
        t.save()

        t.multi.sub1 = 'qqq'
        t.multi.multi2.sub2 = 75

        assert t.multi.sub1 == 'qqq'
        assert t.multi.multi2.sub2 == 75
        assert t.params == {
            '_class': 'devops.tests.models.test_base:MyMultiModel',
            'multi': {
                'sub1': 'qqq',
                'multi2': {'sub2': 75}
            }
        }
