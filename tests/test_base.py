"""test_base

Fixtures for testing

created 10-oct-2019 by richb@instantlinux.net
"""

import fakeredis
import os
import pytest
import tempfile
import unittest

from apicrud import initialize
from apicrud.test.base import TestBaseMixin, test_globals
import controllers
from main import application
from example import models

unittest.util._MAX_LENGTH = 2000


class TestBase(TestBaseMixin, unittest.TestCase):

    @pytest.fixture(scope='session', autouse=True)
    def initial_setup(self):
        if not test_globals:
            test_globals['app'] = application.app
            test_globals['dbfile'] = tempfile.mkstemp(prefix='_db')[1]
            db_url = os.environ.get(
                'DB_URL', 'sqlite:///%s' % test_globals['dbfile'])
            path = os.path.abspath(os.path.join(os.path.dirname(
                __file__), '..', 'example'))
            db_seed_file = os.path.join(path, '..', 'tests', 'data',
                                        'db_fixture.yaml')
            test_globals['redis'] = redis_conn = fakeredis.FakeStrictRedis(
                server=fakeredis.FakeServer())
            initialize.app(
                application, controllers, models, path,
                db_seed_file=db_seed_file, db_url=db_url,
                redis_conn=redis_conn)
            self.baseSetup()
        yield test_globals
        try:
            if os.environ.get('DBCLEAN', None) != '0':
                os.remove(test_globals['dbfile'])
        except FileNotFoundError:
            # TODO this is getting called for each test class
            # (thought scope='session' would invoke only once)
            pass

    @classmethod
    def setUpClass(cls):
        cls.classSetup(cls)
