"""test_oauth2

Tests for oauth2

created 26-apr-2021 by richb@instantlinux.net
"""
from authlib.integrations import flask_client
from authlib.common.security import generate_token
from authlib.jose import JsonWebKey
import base64
from datetime import datetime, timedelta
from flask_babel import _
import httpretty
import json
import jwt
import os
from unittest import mock
from urllib.parse import parse_qs, urlparse
import yaml

from apicrud.auth.oauth2_func import oauth2_init
from apicrud.utils import identity_normalize
import test_base


class TestAuth(test_base.TestBase):

    def setUp(self):
        os.environ['GOOGLE_CLIENT_ID'] = (
            '81427209327-c9674sudcht4aah93bkbpnl0'
            '1np7fake.apps.googleusercontent.com')
        os.environ['GOOGLE_CLIENT_SECRET'] = 'Xv-r5yOgDCquIUMqt33Rfake'
        fixture_path = os.path.join(os.path.dirname(os.path.abspath(
            __file__)), 'data')
        self.code = ('4%2F0AY0e-g5kPv0ekCxPxaiUnrggLHmgNRPhA'
                     'PwrUQkXJSpfv4NtBf1Ck7_gMdo6ZWpV3Mfake')
        self.nonce = generate_token()
        self.privatekey = open(
            os.path.join(fixture_path, 'jwt.pem'), 'rb').read()
        self.publickey = open(
            os.path.join(fixture_path, 'jwt.pub'), 'rb').read()
        self.openid_cert = dict(
            kid='69ed57f424491282a18020fd585954b70bb45ae0',
            **JsonWebKey.import_key(self.publickey, dict(kty='RSA')).as_dict())
        self.scope = ('email+profile+openid+https%3A%2F%2Fwww.googleapis.com'
                      '%2Fauth%2Fuserinfo.email+https%3A%2F'
                      '%2Fwww.googleapis.com%2Fauth%2Fuserinfo.profile')

        with open(os.path.join(fixture_path, 'oauth2_response.yaml'), 'rt',
                  encoding='utf8') as f:
            self.data = yaml.safe_load(f)

        httpretty.enable(allow_net_connect=False)
        httpretty.register_uri(
            httpretty.GET,
            'https://accounts.google.com/.well-known/openid-configuration',
            body=json.dumps(self.data['openid_google']),
            content_type='application/json')
        httpretty.register_uri(
            httpretty.GET,
            self.data['openid_google']['authorization_endpoint'],
            status=302, body='')
        httpretty.register_uri(
            httpretty.GET, self.data['openid_google']['jwks_uri'],
            body=json.dumps([self.openid_cert]),
            content_type='application/json')

        oauth2_init(self.app)

    def tearDown(self):
        httpretty.reset()
        httpretty.disable()

    def _tokenreg(self, usermeta, provider='google'):
        """Helper function to generate token data and register with
        token endpoint
        """
        tokendata = dict(
            access_token='abcdef',
            expires_in=120,
            id_token=jwt.encode(usermeta, self.privatekey,
                                headers=dict(
                                    kid=self.openid_cert['kid']),
                                algorithm='RS256'),
            scope='openid email profile',
            token_type='Bearer'
        )
        if 'server_metadata_url' in self.config.AUTH_PARAMS[provider]:
            endpoint = self.data['openid_%s' % provider]['token_endpoint']
        else:
            endpoint = self.config.AUTH_PARAMS[provider]['access_token_url']
        httpretty.register_uri(
            httpretty.POST, endpoint,
            body=json.dumps(tokendata), content_type='application/json')
        return tokendata

    def test_oauth2_policy_auto(self):
        """Login with OAuth2 using mocked request/response handshake
        actions defined using httpretty
        """
        identity = identity_normalize(self.data['users'][0]['email'])
        usermeta = dict(self.data['users'][0], **dict(
            identity=identity,
            iat=int(datetime.utcnow().timestamp()),
            exp=int((datetime.utcnow() + timedelta(seconds=60)).timestamp()),
            nonce=self.nonce))

        response = self.call_endpoint('/auth', 'post', data=dict(
            method='google', nonce=self.nonce))

        redir_uri = response.get_json().get('location')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(urlparse(redir_uri).hostname, 'accounts.google.com')

        self._tokenreg(usermeta)
        _state = parse_qs(urlparse(redir_uri).query).get('state')[0]

        # Callback using the state, nonce, token, and expiry values
        # calculated above. This will create a new user account and
        # login with user access permissions.

        response = self.call_endpoint(
            '/auth_callback/google?state={state}&code={code}'
            '&scope={scope}&authuser=0&prompt=none'.format(
                state=_state, code=self.code, scope=self.scope), 'get')
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

    def test_oauth2_policy_open(self):
        identity = identity_normalize(self.data['users'][1]['email'])
        usermeta = dict(self.data['users'][1], **dict(
            identity=identity,
            iat=int(datetime.utcnow().timestamp()),
            exp=int((datetime.utcnow() + timedelta(seconds=60)).timestamp()),
            nonce=self.nonce))
        usermeta['email'] = identity

        response = self.call_endpoint('/auth', 'post', data=dict(
            method='google', nonce=self.nonce))
        redir_uri = response.get_json().get('location')
        _state = parse_qs(urlparse(redir_uri).query).get('state')[0]
        self._tokenreg(usermeta)
        with self.config_overrides(login_external_policy='open'):
            response = self.call_endpoint(
                '/auth_callback/google?state={state}&code={code}'
                '&scope={scope}&authuser=0&prompt=none'.format(
                    state=_state, code=self.code, scope=self.scope), 'get')
            self.assertEqual(response.status_code, 200)

    def test_oauth2_policy_closed(self):
        identity = identity_normalize('altuser@gmail.com')
        usermeta = dict(self.data['users'][0], **dict(
            identity=identity,
            iat=int(datetime.utcnow().timestamp()),
            exp=int((datetime.utcnow() + timedelta(seconds=60)).timestamp()),
            nonce=self.nonce))
        usermeta['email'] = identity

        response = self.call_endpoint('/auth', 'post', data=dict(
            method='google', nonce=self.nonce))
        redir_uri = response.get_json().get('location')
        _state = parse_qs(urlparse(redir_uri).query).get('state')[0]
        self._tokenreg(usermeta)
        with self.config_overrides(login_external_policy='closed'):
            response = self.call_endpoint(
                '/auth_callback/google?state={state}&code={code}'
                '&scope={scope}&authuser=0&prompt=none'.format(
                    state=_state, code=self.code, scope=self.scope), 'get')
            self.assertEqual(response.status_code, 403)

    def test_oauth2_policy_onrequest(self):
        identity = identity_normalize('requser@gmail.com')
        usermeta = dict(self.data['users'][0], **dict(
            identity=identity,
            iat=int(datetime.utcnow().timestamp()),
            exp=int((datetime.utcnow() + timedelta(seconds=60)).timestamp()),
            nonce=self.nonce))
        usermeta['email'] = identity

        response = self.call_endpoint('/auth', 'post', data=dict(
            method='google', nonce=self.nonce))
        redir_uri = response.get_json().get('location')
        _state = parse_qs(urlparse(redir_uri).query).get('state')[0]
        self._tokenreg(usermeta)
        with self.config_overrides(login_external_policy='onrequest'):
            response = self.call_endpoint(
                '/auth_callback/google?state={state}&code={code}'
                '&scope={scope}&authuser=0&prompt=none'.format(
                    state=_state, code=self.code, scope=self.scope), 'get')
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.get_json()['message'], 'unimplemented')

    def test_oauth2_identity_invalid(self):
        identity = identity_normalize(self.data['users'][0]['email'])
        usermeta = dict(self.data['users'][0], **dict(
            identity=identity,
            iat=int(datetime.utcnow().timestamp()),
            exp=int((datetime.utcnow() + timedelta(seconds=60)).timestamp()),
            nonce=self.nonce))
        usermeta['email'] = 'not-an-email'

        response = self.call_endpoint('/auth', 'post', data=dict(
            method='google', nonce=self.nonce))
        redir_uri = response.get_json().get('location')
        _state = parse_qs(urlparse(redir_uri).query).get('state')[0]
        self._tokenreg(usermeta)
        response = self.call_endpoint(
            '/auth_callback/google?state={state}&code={code}'
            '&scope={scope}&authuser=0&prompt=none'.format(
                state=_state, code=self.code, scope=self.scope), 'get')
        self.assertEqual(response.status_code, 403)

    def test_oauth2_disabled_account(self):
        identity = 'badboy@gmail.com'
        record = dict(
            name='Ronald Johnson', identity='rj@gmail.com', username='rjson')

        response = self.call_endpoint('/account', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        self.authorize(username=self.admin_name, password=self.admin_pw)
        response = self.call_endpoint('/contact?filter={"uid":"%s"}' %
                                      response.get_json()['uid'], 'get')
        self.assertEqual(response.status_code, 200)
        id = response.get_json()['items'][0]['id']
        response = self.call_endpoint('/contact/%s' % id, 'put',
                                      dict(info=identity, status='disabled',
                                           type='email'))
        self.assertEqual(response.status_code, 200)
        usermeta = dict(self.data['users'][0], **dict(
            identity=identity,
            iat=int(datetime.utcnow().timestamp()),
            exp=int((datetime.utcnow() + timedelta(seconds=60)).timestamp()),
            nonce=self.nonce))
        usermeta['email'] = identity
        response = self.call_endpoint('/auth', 'post', data=dict(
            method='google', nonce=self.nonce))
        redir_uri = response.get_json().get('location')
        _state = parse_qs(urlparse(redir_uri).query).get('state')[0]
        self._tokenreg(usermeta)
        response = self.call_endpoint(
            '/auth_callback/google?state={state}&code={code}'
            '&scope={scope}&authuser=0&prompt=none'.format(
                state=_state, code=self.code, scope=self.scope), 'get')
        self.assertEqual(response.status_code, 403)

    @mock.patch('apicrud.SessionAuth.register')
    def test_oauth2_registration_error(self, mock_register):
        identity = 'difficultchild@gmail.com'
        mock_register.return_value = dict(message='testing'), 400

        usermeta = dict(self.data['users'][0], **dict(
            identity=identity,
            iat=int(datetime.utcnow().timestamp()),
            exp=int((datetime.utcnow() + timedelta(seconds=60)).timestamp()),
            nonce=self.nonce))
        usermeta['email'] = identity
        response = self.call_endpoint('/auth', 'post', data=dict(
            method='google', nonce=self.nonce))
        redir_uri = response.get_json().get('location')
        _state = parse_qs(urlparse(redir_uri).query).get('state')[0]
        self._tokenreg(usermeta)
        response = self.call_endpoint(
            '/auth_callback/google?state={state}&code={code}'
            '&scope={scope}&authuser=0&prompt=none'.format(
                state=_state, code=self.code, scope=self.scope), 'get')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['message'], 'testing')

    @mock.patch('apicrud.SessionAuth.register')
    def test_oauth2_open_registration_error(self, mock_register):
        identity = 'secondchild@gmail.com'
        mock_register.return_value = dict(message='testing'), 400

        usermeta = dict(self.data['users'][0], **dict(
            identity=identity,
            iat=int(datetime.utcnow().timestamp()),
            exp=int((datetime.utcnow() + timedelta(seconds=60)).timestamp()),
            nonce=self.nonce))
        usermeta['email'] = identity
        response = self.call_endpoint('/auth', 'post', data=dict(
            method='google', nonce=self.nonce))
        redir_uri = response.get_json().get('location')
        _state = parse_qs(urlparse(redir_uri).query).get('state')[0]
        self._tokenreg(usermeta)
        with self.config_overrides(login_external_policy='open'):
            response = self.call_endpoint(
                '/auth_callback/google?state={state}&code={code}'
                '&scope={scope}&authuser=0&prompt=none'.format(
                    state=_state, code=self.code, scope=self.scope), 'get')
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get_json()['message'], 'testing')

    @mock.patch('authlib.integrations.flask_client.'
                'FlaskRemoteApp.authorize_access_token')
    def test_oauth2_token_error(self, mock_token):
        identity = 'notatoken@gmail.com'
        usermeta = dict(self.data['users'][0], **dict(
            identity=identity,
            iat=int(datetime.utcnow().timestamp()),
            exp=int((datetime.utcnow() + timedelta(seconds=60)).timestamp()),
            nonce=self.nonce))
        usermeta['email'] = identity
        response = self.call_endpoint('/auth', 'post', data=dict(
            method='google', nonce=self.nonce))
        redir_uri = response.get_json().get('location')
        _state = parse_qs(urlparse(redir_uri).query).get('state')[0]
        self._tokenreg(usermeta)
        mock_token.side_effect = flask_client.OAuthError
        response = self.call_endpoint(
            '/auth_callback/google?state={state}&code={code}'
            '&scope={scope}&authuser=0&prompt=none'.format(
                state=_state, code=self.code, scope=self.scope), 'get')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), dict(
            message=_(u'openid client failure')))

    @mock.patch('authlib.integrations.flask_client.OAuth.create_client')
    def test_oauth2_client_error(self, mock_client):
        identity = 'notatoken@gmail.com'
        usermeta = dict(self.data['users'][0], **dict(
            identity=identity,
            iat=int(datetime.utcnow().timestamp()),
            exp=int((datetime.utcnow() + timedelta(seconds=60)).timestamp()),
            nonce=self.nonce))
        usermeta['email'] = identity
        mock_client.side_effect = RuntimeError
        response = self.call_endpoint('/auth', 'post', data=dict(
            method='google', nonce=self.nonce))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(),
                         dict(message=_(u'login client missing')))

    def test_oauth2_secondary_contact(self):
        identity = 'secondarycontact@gmail.com'
        record = dict(
            carrier=None, label='home', type='email', privacy='invitee',
            info=identity, uid=self.test_uid)
        self.authorize()
        response = self.call_endpoint('/contact', 'post', data=record)
        self.assertEqual(response.status_code, 201)

        usermeta = dict(self.data['users'][0], **dict(
            identity=identity,
            iat=int(datetime.utcnow().timestamp()),
            exp=int((datetime.utcnow() + timedelta(seconds=60)).timestamp()),
            nonce=self.nonce))
        usermeta['email'] = identity

        response = self.call_endpoint('/auth', 'post', data=dict(
            method='google', nonce=self.nonce))
        redir_uri = response.get_json().get('location')
        _state = parse_qs(urlparse(redir_uri).query).get('state')[0]
        self._tokenreg(usermeta)
        response = self.call_endpoint(
            '/auth_callback/google?state={state}&code={code}'
            '&scope={scope}&authuser=0&prompt=none'.format(
                state=_state, code=self.code, scope=self.scope), 'get')
        self.assertEqual(response.status_code, 302)

        tok = jwt.decode(
            response.location.split('#')[1].split('=')[1],
            self.config.JWT_SECRET, algorithms=['HS256'])
        self.assertEqual(tok['identity'], self.test_email)

    """
    # TODO these tests trigger RuntimeError: Missing "jwks_uri" in metadata
    def test_oauth2_github(self):
        os.environ['GITHUB_CLIENT_ID'] = '42fab9bcd671453bfake'
        os.environ['GITHUB_CLIENT_SECRET'] = (
            '17db7669573f40f9b06c00a340ea8c6511d2fake')
        oauth2_init(self.app)
        provider = 'github'
        httpretty.register_uri(
            httpretty.GET,
            self.config.AUTH_PARAMS[provider]['authorize_url'],
            status=302)
        self.scope = quote_plus(self.config.AUTH_PARAMS[provider][
            'client_kwargs']['scope'])
        identity = identity_normalize(self.data['users'][3]['email'])
        usermeta = dict(self.data['users'][3], **dict(
            identity=identity,
            iat=int(datetime.utcnow().timestamp()),
            exp=int((datetime.utcnow() + timedelta(seconds=60)).timestamp()),
            nonce=self.nonce))
        usermeta['email'] = identity

        response = self.call_endpoint('/auth', 'post', data=dict(
            method=provider, nonce=self.nonce))
        redir_uri = response.get_json().get('location')
        _state = parse_qs(urlparse(redir_uri).query).get('state')[0]
        self.assertRegex(_state, '^[a-zA-Z0-9]{30}$')
        self._tokenreg(usermeta, provider=provider)

        response = self.call_endpoint(
            '/auth_callback/github?state={state}&code={code}'
            '&scope={scope}&authuser=0&prompt=none'.format(
                state=_state, code=self.code, scope=self.scope), 'get')
        self.assertEqual(response.status_code, 200)

    def test_oauth2_slack(self):
        os.environ['SLACK_CLIENT_ID'] = '1922374891962.194156017fake'
        os.environ['SLACK_CLIENT_SECRET'] = 'c85500243266464e924123355fa3fake'
        oauth2_init(self.app)
        provider = 'slack'
        httpretty.register_uri(
            httpretty.GET,
            self.config.AUTH_PARAMS[provider]['authorize_url'],
            status=302)
        self.scope = quote_plus(self.config.AUTH_PARAMS[provider][
            'client_kwargs']['scope'])
        identity = identity_normalize(self.data['users'][2][
            'user']['profile']['email'])
        usermeta = dict(self.data['users'][2], **dict(
            identity=identity,
            iat=int(datetime.utcnow().timestamp()),
            exp=int((datetime.utcnow() + timedelta(seconds=60)).timestamp()),
            nonce=self.nonce))
        usermeta['email'] = identity

        response = self.call_endpoint('/auth', 'post', data=dict(
            method=provider, nonce=self.nonce))
        redir_uri = response.get_json().get('location')
        _state = parse_qs(urlparse(redir_uri).query).get('state')[0]
        self.assertRegex(_state, '^[a-zA-Z0-9]{30}$')
        self._tokenreg(usermeta, provider=provider)

        response = self.call_endpoint(
            '/auth_callback/slack?state={state}&code={code}'
            '&scope={scope}&authuser=0&prompt=none'.format(
                state=_state, code=self.code, scope=self.scope), 'get')
        self.assertEqual(response.status_code, 200)
    """
