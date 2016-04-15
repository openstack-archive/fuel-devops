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

from xml.dom import minidom
from xml.etree import ElementTree as ET

import six


class XMLGeneratorElement(object):

    def __init__(self, name, parent, builder):
        self.elem = ET.SubElement(parent, name)
        self.parent = parent
        self.builder = builder
        self.prev_elem = None

    def __enter__(self):
        self.prev_elem = self.builder.curr_el
        self.builder.curr_el = self.elem

    def __exit__(self, *args):
        self.builder.curr_el = self.prev_elem
        self.prev_elem = None

    def __getattr__(self, name):
        return XMLGeneratorElement(
            name=name,
            parent=self.elem,
            builder=self.builder)

    def __call__(self, txt=None, **kwargs):
        # update attributes
        kwargs = {k: str(v) for k, v in kwargs.items()}
        self.elem.attrib.update(kwargs)

        # update text if any
        if txt:
            self.elem.text = str(txt)

        return self


@six.python_2_unicode_compatible
class XMLGenerator(object):

    def __init__(self, root_name, **kwargs):
        self.root = ET.Element(root_name)
        kwargs = {k: str(v) for k, v in kwargs.items()}
        self.root.attrib.update(kwargs)
        self.curr_el = self.root

    def __getattr__(self, name):
        return XMLGeneratorElement(
            name=name,
            parent=self.curr_el,
            builder=self)

    def __str__(self):
        rough_string = ET.tostring(self.root, encoding='utf-8')
        reparsed = minidom.parseString(rough_string)
        s = reparsed.toprettyxml(indent='    ', encoding='utf-8')
        if six.PY2:
            return s
        else:
            return str(s, encoding='utf-8')
