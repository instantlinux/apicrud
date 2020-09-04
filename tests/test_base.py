"""test_base

Fixtures for testing

created 10-oct-2019 by richb@instantlinux.net
"""

import base64
import fakeredis
from flask import g
import json
import jwt
import os
import pytest
from sqlalchemy.exc import IntegrityError
import tempfile
import unittest

from apicrud import database, ServiceConfig, SessionManager
from main import application, setup_db
from models import Account, Category, Contact, Person

global_fixture = {}
unittest.util._MAX_LENGTH = 2000


class TestBase(unittest.TestCase):

    @pytest.fixture(scope='session', autouse=True)
    def initial_setup(self):
        if not global_fixture:
            global_fixture['app'] = application.app
            global_fixture['dbfile'] = tempfile.mkstemp(prefix='_db')[1]
            db_url = os.environ.get(
                'DB_URL', 'sqlite:///%s' % global_fixture['dbfile'])
            global_fixture['config'] = ServiceConfig(db_url=db_url).config
            global_fixture['flask'] = global_fixture['app'].test_client()
            global_fixture['redis'] = fakeredis.FakeStrictRedis(
                server=fakeredis.FakeServer())
            redis_conn = global_fixture['redis']
            unittest.mock.patch(
                'apicrud.service_registry.ServiceRegistry.update').start()
            setup_db(db_url=db_url, redis_conn=redis_conn)

            # TODO figure out how to divert logging under pytest
            # global_fixture['logfile_name'] = tempfile.mkstemp(
            #     prefix='_test')[1]
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
        self.theme_id = 'x-05a720bf'
        self.credentials = {}
        self.authuser = None
        self.settings_id = 'x-75023275'
        self.location_id = 'x-67673434'
        self.default_storage_id = 'x-RwgSVd5G'

        self.username = 'testr'
        self.password = 't0ps3crEt'
        self.account_id = 'x-TpP43xS9'
        self.cat_id = 'x-Jiqag482'
        self.contact_id = 'x-E97yKy73'
        self.test_uid = 'u-B0miQweE'
        self.test_person_name = 'Conclave Tester'
        self.test_email = 'testuser@test.conclave.events'
        db_session = database.get_session(db_url=self.config.DB_URL)
        record = Person(id=self.test_uid, name=self.test_person_name,
                        identity=self.test_email, privacy='public',
                        status='active')
        db_session.add(record)
        record = Contact(id=self.contact_id, uid=self.test_uid,
                         type='email', info=self.test_email,
                         privacy='public', status='active')
        db_session.add(record)
        record = Account(id=self.account_id, name=self.username,
                         uid=self.test_uid, status='active',
                         settings_id=self.settings_id,
                         password=('$5$rounds=535000$HGVkMUlpoWPlgbsN$BqsTg'
                                   'mTmiUXaSLoaiQgEY5IWxNLrA3Y1D2qlzm57hz/'))
        db_session.add(record)
        record = Category(id=self.cat_id, uid=self.test_uid,
                          name='default')
        db_session.add(record)

        self.admin_name = 'testadmin'
        self.admin_pw = 'opens3crEt'
        self.adm_account_id = 'x-6hj1BXEH'
        self.adm_contact_id = 'x-6b1AUgmt'
        self.adm_contact_2 = 'x-P703gZkJ'
        self.adm_cat_id = 'x-1xDjMu6M'
        self.admin_uid = 'u-tMY1b862'
        self.adm_person_name = 'Test Admin'
        self.admin_email = 'admin@test.conclave.events'
        record = Person(id=self.admin_uid, name=self.adm_person_name,
                        identity=self.admin_email, privacy='public',
                        status='active')
        db_session.add(record)
        record = Contact(id=self.adm_contact_id, uid=self.admin_uid,
                         type='email', info=self.admin_email,
                         privacy='public', status='active')
        db_session.add(record)
        record = Contact(id=self.adm_contact_2, uid=self.admin_uid,
                         type='email', info='hidden-adm@test.conclave.events',
                         privacy='member', status='active')
        db_session.add(record)
        record = Account(id=self.adm_account_id, name=self.admin_name,
                         uid=self.admin_uid, status='active',
                         settings_id=self.settings_id, is_admin=True,
                         password=('$5$rounds=535000$e/tKrK5./UWjY8t7$Q.Lak'
                                   '2.1dzkB4tf0aHVSyRbClPKgkzZJZNPeS0e9e31'))
        db_session.add(record)
        record = Category(id=self.adm_cat_id, uid=self.admin_uid,
                          name='default')
        db_session.add(record)
        try:
            db_session.commit()
        except IntegrityError:
            db_session.rollback()
        db_session.remove()

    @classmethod
    def tearDownClass(self):
        # os.remove(self.logfile_name)
        pass

    def authorize(self, username=None, password=None, new_session=False):
        if not username:
            username = self.username
            password = self.password
        if username not in self.credentials or new_session:
            response = self.call_endpoint('/auth', 'post', data=dict(
                username=username, password=password))
            if response.status_code != 201:
                return response.status_code
            tok = jwt.decode(response.get_json()['jwt_token'],
                             self.config.JWT_SECRET, algorithms=['HS256'])
            self.credentials[username] = dict(
                auth='Basic ' + base64.b64encode(
                    bytes(tok['sub'] + ':' + tok['jti'], 'utf-8')
                ).decode('utf-8'))
        self.authuser = username
        return 201

    def call_endpoint(self, endpoint, method, data=None, extraheaders={}):
        """call an endpoint with flask.g context

        params:
          endpoint(str): endpoint path (after base_url)
          method(str): get, post, put etc
          extraheaders(dict): additional headers
        returns:
          http response
        """

        base_url = '/config/v1' if endpoint == '/config' else self.base_url
        with self.app.test_request_context():
            g.db = database.get_session()
            g.session = SessionManager(redis_conn=self.redis)
            headers = extraheaders.copy()
            if self.authuser:
                headers['Authorization'] = self.credentials[
                    self.authuser]['auth']
                headers['Accept'] = 'application/json'
                headers['Content-Type'] = 'application/json'
            if data:
                response = getattr(self.flask, method)(
                    base_url + endpoint, data=json.dumps(data),
                    headers=headers,
                    content_type='application/json')
            else:
                response = getattr(self.flask, method)(
                    base_url + endpoint, headers=headers)
            g.db.remove()
            return response
