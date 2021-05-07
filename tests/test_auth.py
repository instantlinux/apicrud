"""test_auth

Tests for session auth functions

created 10-apr-2021 by richb@instantlinux.net
"""
from ldap3 import Server as LDAPServer, Connection as LDAPConnection
from authlib.common.security import generate_token
from authlib.jose import JsonWebKey
import base64
from datetime import datetime, timedelta
import httpretty
import json
import jwt
import os
from unittest import mock
from urllib.parse import parse_qs, urlparse
import yaml

from apicrud import ServiceRegistry
from apicrud.auth.oauth2_func import oauth2_init
from apicrud.auth.ldap_func import ldap_init
from apicrud.utils import identity_normalize
import test_base


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

    @httpretty.activate
    def test_oauth2(self):
        """Login with OAuth2 using mocked request/response handshake
        actions defined using httpretty
        """
        os.environ['GOOGLE_CLIENT_ID'] = (
            '81427209327-c9674sudcht4aah93bkbpnl0'
            '1np7escv.apps.googleusercontent.com')
        os.environ['GOOGLE_CLIENT_SECRET'] = (
            'Xv-r5yOgDCquIUMqt33RJSkl')
        fixture_path = os.path.join(os.path.dirname(os.path.abspath(
            __file__)), 'data')
        privatekey = open(os.path.join(fixture_path, 'jwt.pem'), 'rb').read()
        publickey = open(os.path.join(fixture_path, 'jwt.pub'), 'rb').read()

        with open(os.path.join(fixture_path, 'openid_google.yaml'), 'rt',
                  encoding='utf8') as f:
            openid_cfg = yaml.safe_load(f)
        with open(os.path.join(fixture_path, 'openid_user.yaml'), 'rt',
                  encoding='utf8') as f:
            usermeta = yaml.safe_load(f)

        openid_cert = dict(
            kid='69ed57f424491282a18020fd585954b70bb45ae0',
            **JsonWebKey.import_key(publickey, dict(kty='RSA')).as_dict())
        identity = identity_normalize(usermeta['email'])
        usermeta['iat'] = int(datetime.utcnow().timestamp())
        usermeta['exp'] = int((datetime.utcnow() + timedelta(
            seconds=60)).timestamp())

        httpretty.HTTPretty.allow_net_connect = False
        httpretty.register_uri(
            httpretty.GET,
            'https://accounts.google.com/.well-known/openid-configuration',
            body=json.dumps(openid_cfg), content_type='application/json')
        httpretty.register_uri(
            httpretty.GET, openid_cfg['authorization_endpoint'],
            status=302, body='')
        httpretty.register_uri(
            httpretty.GET, openid_cfg['jwks_uri'],
            body=json.dumps([openid_cert]), content_type='application/json')
        nonce = generate_token()

        oauth2_init(self.app)
        response = self.call_endpoint('/auth', 'post', data=dict(
            method='google', nonce=nonce))

        redir_uri = response.get_json().get('location')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(urlparse(redir_uri).hostname, 'accounts.google.com')

        usermeta['nonce'] = nonce
        tokendata = {
            'access_token': 'abcdef',
            'expires_in': 120,
            'id_token': jwt.encode(usermeta, privatekey,
                                   headers=dict(kid=openid_cert['kid']),
                                   algorithm='RS256'),
            'scope': 'openid email profile',
            'token_type': 'Bearer'
        }
        httpretty.register_uri(
            httpretty.POST, openid_cfg['token_endpoint'],
            body=json.dumps(tokendata), content_type='application/json')

        _state = parse_qs(urlparse(redir_uri).query).get('state')[0]
        _code = ('4%2F0AY0e-g5kPv0ekCxPxaiUnrggLHmgNRPhA'
                 'PwrUQkXJSpfv4NtBf1Ck7_gMdo6ZWpV3MxS8Q')
        _scope = ('email+profile+openid+https%3A%2F%2Fwww.googleapis.com'
                  '%2Fauth%2Fuserinfo.email+https%3A%2F%2Fwww.googleapis.com'
                  '%2Fauth%2Fuserinfo.profile')

        # Callback using the state, nonce, token, and expiry values
        # calculated above. This will create a new user account and
        # login with user access permissions.

        response = self.call_endpoint(
            '/auth_callback/google?state={state}&code={code}'
            '&scope={scope}&authuser=0&prompt=none'.format(
                state=_state, code=_code, scope=_scope), 'get')
        self.assertEqual(response.status_code, 302)

        tok = jwt.decode(
            response.location.split('#')[1].split('=')[1],
            self.config.JWT_SECRET, algorithms=['HS256'])
        self.assertEqual(tok['auth'], 'user')
        self.assertEqual(tok['identity'], identity)
        self.assertEqual(tok['method'], 'google')

        # Get the sub/jti credentials and verify we have permission
        # to read settings object, then confirm the callback url matches
        self.authuser = identity
        self.credentials[identity] = dict(
            auth='Basic ' + base64.b64encode(
                bytes(tok['sub'] + ':' + tok['jti'], 'utf-8')
            ).decode('utf-8'))
        settings = self.call_endpoint('/settings/x-75023275', 'get')
        self.assertEqual(settings.status_code, 200)
        self.assertEqual('http://' + urlparse(response.location).netloc,
                         settings.get_json().get('url'))

        # Try another identity, with external policy open instead of auto

        nonce = generate_token()
        response = self.call_endpoint('/auth', 'post', data=dict(
            method='google', nonce=nonce))
        redir_uri = response.get_json().get('location')
        _state = parse_qs(urlparse(redir_uri).query).get('state')[0]
        usermeta['email'] = 'newuser2@gmail.com'
        usermeta['nonce'] = nonce
        tokendata['id_token'] = jwt.encode(
            usermeta, privatekey, headers=dict(kid=openid_cert['kid']),
            algorithm='RS256')
        httpretty.register_uri(
            httpretty.POST, openid_cfg['token_endpoint'],
            body=json.dumps(tokendata), content_type='application/json')
        with self.config_overrides(login_external_policy='open'):
            response = self.call_endpoint(
                '/auth_callback/google?state={state}&code={code}'
                '&scope={scope}&authuser=0&prompt=none'.format(
                    state=_state, code=_code, scope=_scope), 'get')
            self.assertEqual(response.status_code, 200)

        # Negative test: try another identity, with external policy closed

        nonce = generate_token()
        response = self.call_endpoint('/auth', 'post', data=dict(
            method='google', nonce=nonce))
        redir_uri = response.get_json().get('location')
        _state = parse_qs(urlparse(redir_uri).query).get('state')[0]
        usermeta['email'] = 'altuser@gmail.com'
        usermeta['nonce'] = nonce
        tokendata['id_token'] = jwt.encode(
            usermeta, privatekey, headers=dict(kid=openid_cert['kid']),
            algorithm='RS256')
        httpretty.register_uri(
            httpretty.POST, openid_cfg['token_endpoint'],
            body=json.dumps(tokendata), content_type='application/json')
        with self.config_overrides(login_external_policy='closed'):
            response = self.call_endpoint(
                '/auth_callback/google?state={state}&code={code}'
                '&scope={scope}&authuser=0&prompt=none'.format(
                    state=_state, code=_code, scope=_scope), 'get')
            self.assertEqual(response.status_code, 403)
