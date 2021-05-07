"""test.base

Mixin of shared functions for the TestBase class

created 10-oct-2019 by richb@instantlinux.net
"""
import base64
from collections import namedtuple
from contextlib import contextmanager
from flask import g
import json
import jwt
import os
import tempfile
import unittest
import yaml

from .. import database, service_config, ServiceConfig, SessionManager

test_globals = {}


class TestBaseMixin(object):

    def baseSetup(self):
        """Preliminary initialization: test code should call this once
        at initial pytest startup, after setting up a sqlite or other
        database and invoking initialize.app(). This function starts the
        flask test_client and makes global fixture vars available for
        the setUp classes.
        """
        unittest.mock.patch(
            'apicrud.service_registry.ServiceRegistry.update').start()
        test_globals['config'] = config = ServiceConfig().config
        test_globals['flask'] = test_globals['app'].test_client()
        with open(config.DB_SEED_FILE, 'rt', encoding='utf8') as f:
            records = yaml.safe_load(f)
        test_globals['constants'] = records.get('_constants')

    def classSetup(self):
        """Setup for each test. Instance vars are configured for the
        flask and redis emulators, a mock_messaging object for the
        messaging celery worker, and all the constants found in the
        data/db_fixtures.yaml file.
        """
        self.app = test_globals['app']
        self.config = test_globals['config']
        self.flask = test_globals['flask']
        self.redis = test_globals['redis']
        self.maxDiff = None
        self.base_url = self.config.BASE_URL
        self.credentials = {}
        self.authuser = None
        for item, val in test_globals['constants'].items():
            setattr(self, item, val)

    def authorize(self, username=None, password=None, apikey=None,
                  new_session=False, otp=None):
        """Authorize the specified user

        Args:
          username (str): login name
          password (str): password
          apikey (str): an API key
          new_session (bool): re-use existing session unless this is True
          otp (str): one-time password
        """
        if not username and not apikey:
            username = self.username
            password = self.password
        if apikey:
            response = self.call_endpoint(
                '/apikey?prefix=%s' % apikey[:8], 'get',
                extraheaders={self.config.HEADER_AUTH_APIKEY: apikey})
            if response.status_code == 200:
                self.apikey = apikey
            return response.status_code
        if username not in self.credentials or new_session or otp:
            response = self.call_endpoint('/auth', 'post', data=dict(
                username=username, password=password, otp=otp))
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
            if hasattr(self, 'apikey'):
                headers[self.config.HEADER_AUTH_APIKEY] = self.apikey
                headers['Accept'] = 'application/json'
                headers['Content-Type'] = 'application/json'
            elif self.authuser:
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

    @contextmanager
    def config_overrides(self, **kwargs):
        """Method to override ServiceConfig values, restoring upon
        completion. In normal production, the configuration is
        immutable until restart. This provides a test mechanism to override
        this security-design constraint. Example usage:

        with self.config_overrides(
                login_session_limit=10, login_attempts_max=1):
            ...tests...

        Args:
          kwargs: key/values to set
        Returns:
          (obj): the config object
        """
        config = ServiceConfig().config
        models = ServiceConfig().models
        saved_state = service_config.state.copy()
        saved_config = service_config.config._asdict()
        configfile = tempfile.mkstemp(prefix='_cfg')[1]

        def _restore():
            service_config.state = saved_state
            service_config.config = namedtuple('Struct', [
                key for key in saved_config.keys()])(*saved_config.values())
            os.remove(configfile)

        with open(configfile, 'w') as f:
            yaml.dump(kwargs, f)
        try:
            ret = ServiceConfig(
                file=configfile, reset=True,
                babel_translation_directories=(
                    config.BABEL_TRANSLATION_DIRECTORIES),
                db_seed_file=config.DB_SEED_FILE,
                db_migrations=config.DB_MIGRATIONS,
                models=models, rbac_file=config.RBAC_FILE).config
        except AttributeError:
            _restore()
            raise

        try:
            yield ret
        finally:
            _restore()
