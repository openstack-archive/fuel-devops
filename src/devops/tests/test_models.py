from django.utils import unittest
from devops.models import choices, double_tuple


__author__ = 'vic'

class TestModels(unittest.TestCase):


    def test_django_choices(self):
        self.assertEquals((('a','a'), ('b','b')),double_tuple('a', 'b'))

