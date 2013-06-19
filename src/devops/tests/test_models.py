import random
from django.utils import unittest
import threading
from devops.manager import Manager
from devops.models import double_tuple, Network


class MyThread(threading.Thread):
    def run(self):
        Manager().network_create(str(random.randint(1, 5000)))


class TestModels(unittest.TestCase):
    def test_django_choices(self):
        self.assertEquals((('a', 'a'), ('b', 'b')), double_tuple('a', 'b'))

    def test_concurrency(self):
        threads = [MyThread() for i in xrange(0, 4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        print Network.objects.all()
