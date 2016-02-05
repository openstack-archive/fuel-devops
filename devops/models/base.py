#    Copyright 2013 - 2016 Mirantis, Inc.
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

import abc
from datetime import datetime
import operator

from django.db import models
from django.db.models.base import ModelBase
from django.db.models import query
import jsonfield
import six

from devops.error import DevopsError
from devops.helpers.helpers import deepgetattr
from devops.helpers import loader


def choices(*args, **kwargs):
    defaults = {'max_length': 255, 'null': False}
    defaults.update(kwargs)
    defaults.update(choices=zip(args, args))
    return models.CharField(**defaults)


class BaseModel(models.Model):
    class Meta(object):
        abstract = True

    created = models.DateTimeField(auto_now_add=True, default=datetime.utcnow)


class ParamedModelType(ModelBase):
    """Metaclass of parameterizable class.

    It implements the following functinality:
    * Automaticlly sets Meta.abstract = True for all derived classes
    except the first one.
    * Initializes :class:`ParamFieldBase` classes with `param_key`.
    * Saves the keys of :class:`ParamFieldBase` attributes in
    `_param_field_names` list.
    * Gives an ability to set :class:`ParamFieldBase` values in
    constructor and combine the with other attributes defined in djano
    model.
    * Automaticlly replaces `instance.__class__` fter creation of
    instance in method `__call__`. It is the major thing to make the
    derived models polymorphic.
    """

    def __new__(cls, name, bases, attrs):
        super_new = super(ParamedModelType, cls).__new__

        # if not ParamModel itself
        if name != 'ParamedModel' and name != 'NewBase':
            parents = reduce(operator.add, map(lambda a: a.__mro__, bases))
            # if not a first subclass of ParamedModel
            if ParamedModel not in bases and ParamedModel in parents:
                # add proxy=True by default
                if 'Meta' not in attrs:
                    attrs['Meta'] = type('Meta', (object, ), {})
                Meta = attrs['Meta']
                Meta.proxy = True

        # do django stuff
        new_class = super_new(cls, name, bases, attrs)

        new_class._param_field_names = []

        # initialize ParamField keys
        for attr_name in attrs:
            attr = attrs[attr_name]
            if isinstance(attr, ParamFieldBase):
                attr.set_param_key(attr_name)
                new_class._param_field_names.append(attr_name)

        return new_class

    def __call__(cls, *args, **kwargs):
        # split kwargs which django db are not aware of
        # to separete dict
        kwargs_for_params = {}
        defined_params = cls.get_defined_params()
        for param in defined_params:
            if param in kwargs:
                kwargs_for_params[param] = kwargs.pop(param)

        obj = super(ParamedModelType, cls).__call__(*args, **kwargs)

        if obj._class:
            # we store actual class name in _class attribute
            # so use it to load required class
            Cls = loader.load_class(obj._class)
            # replace base class
            obj.__class__ = Cls

        # set param values
        for param in kwargs_for_params:
            setattr(obj, param, kwargs_for_params[param])

        return obj


@six.add_metaclass(abc.ABCMeta)
class ParamFieldBase(object):
    """Base class for ParamFields."""

    def __init__(self):
        self.param_key = None

    def set_param_key(self, param_key):
        self.param_key = param_key

    @abc.abstractmethod
    def set_default_value(self, instance):
        return

    @abc.abstractmethod
    def __get__(self, instance, cls):
        return

    @abc.abstractmethod
    def __set__(self, instance, values):
        return

    def __delete__(self, instance):
        raise AttributeError("Can't delete attribute")


class ParamField(ParamFieldBase):
    """Field class.

    This class implemets routine of using json field as a storage.
    e.g. if you define a field with name "foo" then its value will be
    stored in `params` json field as {'foo': 'value'}. This class
    allows to avoid direct access to json field and it hides the routine.

    Additionally it gives an ability:
    * to set default value.
    * to limit values using a list of allowed values.

    Examples of ussage::

        class A(ParamedModel):
            foo = ParamField(default=10)
            bar = ParamField(choices=('a', 'b', 'c'))

        a = A()
        print(a.foo)  # prints 10
        print(a.bar)  # prints None

        a.foo = 5
        a.bar = 'c'
        print(a.params)  # prints {'foo': 5, 'bar': 'c'}

        a.bar = 15  # throws DevopsError
    """

    def __init__(self, default=None, choices=None):
        super(ParamField, self).__init__()

        if choices and default not in choices:
            raise DevopsError('Default value not in choices list')

        self.default_value = default
        self.choices = choices

    def set_default_value(self, instance):
        instance.params.setdefault(self.param_key, self.default_value)

    def __get__(self, instance, cls):
        return instance.params.get(self.param_key, self.default_value)

    def __set__(self, instance, value):
        if self.choices and value not in self.choices:
            raise DevopsError('{}: Value not in choices list'
                              ''.format(self.param_key))

        instance.params[self.param_key] = value


class ParamMultiField(ParamFieldBase):
    """Field class which stores other fields.

    Acts the same way as :class:`ParamField` but should be used in case
    if you want to use nested fields.

    Examples of ussage::

        class A(ParamedModel):
            foo = ParamMultiField(
                bar=ParamField(default=10),
                baz=ParamField(),
            )

        a = A()
        print(a.foo.bar)  # prints 10
        print(a.foo.baz)  # prints None

        a.foo.bar = 0
        a.foo.baz = 1
        print(a.params)  # prints {'foo': {'bar': 0, 'baz': 1}}
    """

    def __init__(self, **subfields):
        super(ParamMultiField, self).__init__()

        if len(subfields) == 0:
            raise DevopsError('subfields is empty')

        self.subfields = []
        for name, field in subfields.iteritems():
            if not isinstance(field, (ParamField, ParamMultiField)):
                raise DevopsError('field "{}" has wrong type;'
                                  ' should be ParamField or ParamMultiField'
                                  ''.format(name))
            field.set_param_key(name)
            self.subfields.append(field)

        self.choices = None
        self._proxy = None

        self.proxy_fields = {field.param_key: field
                             for field in self.subfields}
        Proxy = type('ParamMultiFieldProxy', (object, ), self.proxy_fields)
        self._proxy = Proxy()

    def set_default_value(self, instance):
        for field in self.subfields:
            self._init_proxy_params(instance)
            field.set_default_value(self._proxy)

    def _init_proxy_params(self, instance):
        instance.params.setdefault(self.param_key, dict())
        self._proxy.params = instance.params[self.param_key]

    def __get__(self, instance, cls):
        self._init_proxy_params(instance)
        return self._proxy

    def __set__(self, instance, values):
        if not isinstance(values, dict):
            raise DevopsError('Can set only dict')
        self._init_proxy_params(instance)
        for field_name, field_value in values.iteritems():
            if field_name not in self.proxy_fields:
                raise DevopsError('Unknown field "{}"'.format(field_name))
            setattr(self._proxy, field_name, field_value)


class ParamedModelQuerySet(query.QuerySet):
    """Custom QuerySet for ParamedModel"""

    def filter(self, **kwargs):
        super_filter = super(ParamedModelQuerySet, self).filter

        # split kwargs which django db are not aware of
        # to separete dict
        kwargs_for_params = {}
        db_kwargs = {}
        field_names = self.model._meta.get_all_field_names()
        for param in kwargs.keys():
            first_subparam = param.split('__')[0]
            if first_subparam not in field_names:
                kwargs_for_params[param] = kwargs[param]
            else:
                db_kwargs[param] = kwargs[param]

        # filter using db arguments
        queryset = super_filter(**db_kwargs)

        if not kwargs_for_params:
            # return db queryset if there is no params
            return queryset

        # filter using params
        result_ids = []
        for item in queryset:
            for key, value in kwargs_for_params.iteritems():
                # NOTE(astudenov): no support for 'gt', 'lt', 'in'
                # and other django's filter stuff

                item_val = deepgetattr(item, key, splitter='__',
                                       do_raise=True)
                if item_val != value:
                    break
            else:
                result_ids.append(item.id)

        # convert result to new queryset using ids
        return super_filter(id__in=result_ids)


class ParamedModelManager(models.Manager):
    """Manager for ParamedModel"""

    use_for_related_fields = True

    def get_queryset(self):
        return ParamedModelQuerySet(self.model, using=self._db)


class ParamedModel(six.with_metaclass(ParamedModelType, models.Model)):
    """Parameterizable class

    This class allows all derived classes to be polymorphically extended
    by extra fields by using :class:`ParamField` and :class:`ParamMultiField`.
    First derived class of :class:`ParamModel` must be non-abstract to
    create a real database table and all subsequent derived classes are
    atomaticlly marked as abstract by :class:`ParamedModelType`. This is
    made to avoid creation of db tables for derived classes. See mode
    info about how it is implemented in metaclass :class:`ParamedModelType`.

    The class has two fields:
    * params - this is a jsonfield where all extra fields are stored and
               serialized to json string when the instance is saved to db
    * _class - a :class:`ParamField` which stores path to the derived
               class. It allows to load the same derived class after
               loading data from db.
    """

    class Meta(object):
        abstract = True

    objects = ParamedModelManager()

    params = jsonfield.JSONField(default={})
    _class = ParamField()

    @classmethod
    def get_defined_params(cls):
        param_names = []
        for basecls in cls.__mro__:
            if not hasattr(basecls, '_param_field_names'):
                continue
            param_names += basecls._param_field_names
        return param_names

    def set_default_params(self):
        for basecls in self.__class__.__mro__:
            if not hasattr(basecls, '_param_field_names'):
                continue
            for param in basecls._param_field_names:
                basecls.__dict__[param].set_default_value(self)

    def save(self, *args, **kwargs):
        # store current class to _class attribute
        self._class = loader.get_class_path(self)
        self.set_default_params()
        return super(ParamedModel, self).save(*args, **kwargs)
