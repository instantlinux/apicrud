"""test_base

Fixtures for testing

created 10-oct-2019 by richb@instantlinux.net
"""

import fakeredis
import os
import pytest
import tempfile
import unittest
import yaml

from apicrud import initialize, ServiceConfig, SessionAuth
from apicrud.test.base import TestBaseMixin
import controllers
from main import application
from messaging import send_contact
import models

global_fixture = {}
unittest.util._MAX_LENGTH = 2000


class TestBase(TestBaseMixin, unittest.TestCase):

    @pytest.fixture(scope='session', autouse=True)
    def initial_setup(self):
        if not global_fixture:
            global_fixture['app'] = application.app
            global_fixture['dbfile'] = tempfile.mkstemp(prefix='_db')[1]
            db_url = os.environ.get(
                'DB_URL', 'sqlite:///%s' % global_fixture['dbfile'])
            global_fixture['flask'] = global_fixture['app'].test_client()
            global_fixture['redis'] = redis_conn = fakeredis.FakeStrictRedis(
                server=fakeredis.FakeServer())
            unittest.mock.patch(
                'apicrud.service_registry.ServiceRegistry.update').start()
            db_seed_file = os.path.join(os.path.dirname(
                __file__), 'data', 'db_fixture.yaml')
            # TODO consider connection singletons in initialize()
            initialize.app(
                application, controllers, models,
                os.path.join(os.path.dirname(
                    os.path.abspath(__file__)), '..', 'example'),
                db_seed_file=db_seed_file,
                db_url=db_url,
                func_send=send_contact.delay,
                redis_conn=redis_conn)
            global_fixture['config'] = ServiceConfig().config
            with open(db_seed_file, 'rt', encoding='utf8') as f:
                records = yaml.safe_load(f)
            global_fixture['constants'] = records.get('_constants')
            SessionAuth(redis_conn=redis_conn)
        yield global_fixture
        try:
            if os.environ.get('DBCLEAN', None) != '0':
                os.remove(global_fixture['dbfile'])
        except FileNotFoundError:
            # TODO this is getting called for each test class
            # (thought scope='session' would invoke only once)
            pass

    @classmethod
    def setUpClass(self):
        self.app = global_fixture['app']
        self.config = global_fixture['config']
        self.flask = global_fixture['flask']
        self.redis = global_fixture['redis']
        self.maxDiff = None
        self.base_url = self.config.BASE_URL
        self.credentials = {}
        self.authuser = None
        for item, val in global_fixture['constants'].items():
            setattr(self, item, val)
