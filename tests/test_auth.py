"""test_auth

Tests for session auth functions

created 10-apr-2021 by richb@instantlinux.net
"""
from ldap3 import Server as LDAPServer, Connection as LDAPConnection
import os
from unittest import mock

from apicrud import ServiceRegistry
from apicrud.auth.ldap_func import ldap_init
import test_base


class TestAuth(test_base.TestBase):

    def test_auth_params(self):
        expected = dict(
            account_id=self.account_id, uid=self.test_uid,
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

        os.environ['GOOGLE_CLIENT_ID'] = (
            '81427209327-c9674sudcht4aah93bkbpnl0'
            '1np7escv.apps.googleusercontent.com')
        with self.config_overrides(auth_methods=['oauth2']):
            response = self.call_endpoint('/auth_methods', 'get')
            self.assertEqual(response.status_code, 200)
            result = response.get_json()
            self.assertEqual(result['policies']['login_internal'], 'closed')
            self.assertIn('google', result.get('items'))

    def test_bad_auth_method(self):
        response = self.call_endpoint('/auth', 'post', data=dict(
            username='test1', password='Abcdef!01', method='invalid'))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), dict(
            message=u'unsupported login method'))

    def test_ldap(self):
        params = dict(domain='example', servers=['test1'],
                      search_base='CN=Users,DC=test,DC=example,DC=com')

        server = LDAPServer('test1')
        conn = LDAPConnection(server, user='cn=testuser,ou=test,o=unit',
                              password='secret', client_strategy='MOCK_SYNC')
        conn.strategy.entries_from_json(os.path.join(os.path.dirname(
            __file__), '..', 'tests', 'data', 'ldap_entries.json'))
        mock_conn = mock.Mock()
        mock_conn.bind.return_value = True
        mock_conn.unbind.return_value = None
        with self.config_overrides(auth_methods=['ldap'], ldap_params=params):
            ldap_init(ldap_conn=conn, ldap_mock=mock_conn)
            response = self.call_endpoint('/auth', 'post', data=dict(
                username='ldapuser', password='Fedcba!99'))
            self.assertEqual(response.status_code, 201)
            mock_conn.bind.assert_called_with()

            # Negative test: rejected user
            mock_conn.bind.return_value = False
            response = self.call_endpoint('/auth', 'post', data=dict(
                username='superuser', password='Soop3rSekr!t'))
            self.assertEqual(response.status_code, 403)

        # Negative test: user not in authorized group
        with self.config_overrides(auth_methods=['ldap'], ldap_params=dict(
                search_base='CN=SuperUsers,DC=test,DC=example,DC=com')):
            mock_conn.bind.return_value = True
            response = self.call_endpoint('/auth', 'post', data=dict(
                username='ldapuser', password='Fedcba!99'))
            self.assertEqual(response.status_code, 403)
