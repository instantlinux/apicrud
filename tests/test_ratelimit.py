"""test_ratelimit

Tests for rate limit

created 1-jan-2021 by richb@instantlinux.net
"""

from flask import g
import pytest
from redis.exceptions import ConnectionError, DataError
from unittest import mock

import test_base
from apicrud import database, RateLimit


class TestRateLimit(test_base.TestBase):

    def setUp(self):
        self.authorize(username=self.admin_name, password=self.admin_pw)

    @pytest.mark.slow
    def test_set_max_verify(self):
        account = dict(name='Robert Morris', username='rmorris',
                       identity='rmorris@conclave.events')
        password = dict(new_password='x73eZrW9', verify_password='x73eZrW9')
        expected = dict(error=dict(code=429, status='Too Many Requests'),
                        message=('This user has exceeded an allotted request '
                                 'count. Try again later.'))
        maxcalls = 3

        # Make a new account
        response = self.call_endpoint('/account', 'post', data=account)
        self.assertEqual(response.status_code, 201)
        acc = response.get_json()['id']
        uid = response.get_json()['uid']

        for call in self.mock_messaging.call_args_list:
            password['reset_token'] = call.kwargs.get('token')
        response = self.call_endpoint(
            '/account_password/%s' % uid, 'put', data=password)
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))

        # Set the account's ratelimit
        record = dict(name='ratelimit', value=str(maxcalls), uid=uid)
        response = self.call_endpoint('/grant', 'post', data=record)
        self.assertEqual(response.status_code, 201)

        # Authorize and test the limit
        self.authorize(username=account['username'],
                       password=password['new_password'], new_session=True)
        for call in range(maxcalls):
            response = self.call_endpoint('/account/%s' % acc, 'get')
            self.assertEqual(response.status_code, 200)
        response = self.call_endpoint('/account/%s' % acc, 'get')
        self.assertEqual(response.status_code, 429, 'expecting rate-limit')
        self.assertEqual(response.get_json(), expected)

        # Turn off rate-limiting and re-try
        with self.config_overrides(ratelimit_enable=False):
            response = self.call_endpoint('/account/%s' % acc, 'get')
            self.assertEqual(response.status_code, 200)

    @mock.patch('logging.error')
    @mock.patch('redis.Redis.pipeline')
    @mock.patch('redis.Redis.get')
    def test_ratelimit_exceptions(self, mock_get, mock_pipeline, mock_error):

        with self.app.test_request_context():
            g.db = database.get_session()

            self.assertFalse(RateLimit().call(uid=None),
                             msg='Anonymous requests should not be limited')

            mock_get.side_effect = ConnectionError('testlimit')
            self.assertFalse(RateLimit().call(uid=self.test_uid))
            mock_error.assert_called_with(dict(action='ratelimit.call',
                                               message='testlimit'))
            mock_get.side_effect = None

            mock_pipeline.side_effect = DataError('key not set')
            self.assertFalse(RateLimit().call(uid=self.test_uid))
            mock_error.assert_called_with(dict(action='ratelimit.call',
                                               message='key not set'))
            g.db.remove()
