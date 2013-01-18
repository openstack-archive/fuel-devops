from django.utils import unittest
from devops.models import double_tuple


class TestModels(unittest.TestCase):


    def test_django_choices(self):
        self.assertEquals((('a','a'), ('b','b')),double_tuple('a', 'b'))

