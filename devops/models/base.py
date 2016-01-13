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

from datetime import datetime
import operator

from django.db import models
from django.db.models.base import ModelBase
import jsonfield
import six

from devops.error import DevopsError
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
    """TODO"""

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


class ParamFieldBase(object):
    """TODO"""

    def __init__(self):
        self.param_key = None

    def set_param_key(self, param_key):
        self.param_key = param_key

    def __delete__(self, instance):
        raise AttributeError("Can't delete attribute")


class ParamField(ParamFieldBase):
    """TODO"""

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
    """TODO"""

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


class ParamedModel(six.with_metaclass(ParamedModelType, models.Model)):
    """TODO"""

    class Meta(object):
        abstract = True

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
