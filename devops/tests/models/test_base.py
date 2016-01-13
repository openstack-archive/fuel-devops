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

from django.test import TestCase

from devops.error import DevopsError
from devops.models.base import ParamField
from devops.models.base import ParamMultiField
from devops.models import Driver


class MyModel(Driver):

    field = ParamField(default=10)
    number = ParamField(default=None, choices=(None, 'one', 'two'))
    multi = ParamMultiField(
        sub1=ParamField(default='abc'),
        sub2=ParamField(default=15, choices=(11, 13, 15)),
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

        t2 = Driver.objects.get(name='test_driver_model')
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
        with self.assertRaises(DevopsError):
            MyModel(multi=dict(unknown='aaa'))
        with self.assertRaises(DevopsError):
            MyModel(multi='aaa')

    def test_not_in_choices(self):
        with self.assertRaises(DevopsError):
            MyModel(number=0)
        with self.assertRaises(DevopsError):
            t = MyModel()
            t.number = 0
        with self.assertRaises(DevopsError):
            MyModel(multi=dict(sub2='aaa'))
        with self.assertRaises(DevopsError):
            t = MyModel()
            t.multi.sub2 = 'aaa'


class MyMultiModel(Driver):

    multi = ParamMultiField(
        sub1=ParamField(default='abc'),
        multi2=ParamMultiField(
            sub2=ParamField(default=13),
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
