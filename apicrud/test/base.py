"""test.base

Mixin of shared functions for the TextBase class

created 10-oct-2019 by richb@instantlinux.net
"""
import base64
from flask import g
import json
import jwt

from .. import database, SessionManager


class TestBaseMixin(object):

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
