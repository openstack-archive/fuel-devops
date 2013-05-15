from unittest import TestCase
from devops.error import DevopsCalledProcessError


class TestManager(TestCase):
    def test(self):
        raise DevopsCalledProcessError('asdf', 1, ['a', 'b'] + ['b', 'c'])

    def test2(self):
        raise DevopsCalledProcessError('asdf', 1)
