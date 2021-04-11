"""test_auth

Tests for session auth functions

created 10-apr-2021 by richb@instantlinux.net
"""
import test_base

from apicrud import ServiceRegistry
from apicrud.session_auth import Ocache


class TestAuth(test_base.TestBase):

    def test_auth_params(self):
        expected = dict(
            resources=ServiceRegistry().find()['url_map'],
            settings_id=self.settings_id, totp=False)

        self.authorize()
        response = self.call_endpoint('/auth_params', 'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), expected)

    def test_auth_methods(self):
        expected_policies = dict(login_external='auto', login_internal='open')

        response = self.call_endpoint('/auth_methods', 'get')
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertGreaterEqual(result.get('count'), 1)
        self.assertIn('local', result.get('items'))
        self.assertEqual(expected_policies, result.get('policies'))

    def test_auth_ocache(self):
        cache = Ocache()
        cache.set('test1', 'abc')
        self.assertEqual(cache.get('test1'), 'abc')
        self.assertIsNone(cache.get('invalid'))
