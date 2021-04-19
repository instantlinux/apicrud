"""test_totp

Tests for auth TOTP

created 6-apr-2021 by richb@instantlinux.net
"""

import pyotp
import pytest
from unittest import mock

import test_base

from apicrud import database
from models import Account


class TestAuthTOTP(test_base.TestBase):
    @mock.patch('messaging.send_contact.delay')
    def test_totp_generate_reg(self, mock_messaging):
        """Generate and register a token"""

        account = dict(name='IT Admin', username='theboss',
                       identity='theboss@example.com')
        expected = dict(
            is_admin=False, name=account['username'], owner=account['name'],
            password_must_change=False, rbac='dru', status='active',
            totp=False, settings_id=self.settings_id)
        password = dict(new_password='a049bcd-8', verify_password='a049bcd-8')

        response = self.call_endpoint('/account', 'post', data=account)
        self.assertEqual(response.status_code, 201)
        acc = response.get_json()['id']
        uid = response.get_json()['uid']

        for call in mock_messaging.call_args_list:
            password['reset_token'] = call.kwargs.get('token')
        response = self.call_endpoint(
            '/account_password/%s' % uid, 'put', data=password)
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))
        self.authorize(username=account['username'],
                       password=password['new_password'], new_session=True)

        response = self.call_endpoint('/auth_totp', 'get')
        result = response.get_json()
        self.assertEqual(response.status_code, 200)
        nonce = result['jti']
        otp = pyotp.TOTP(result['totp']).now()
        self.assertEqual(result['auth'], 'pendingtotp')
        self.assertRegex(result['uri'],
                         '^otpauth://totp/[A-Za-z]+:theboss%40example.com[?]+'
                         'secret=[A-Z0-9]{32}&issuer=[A-Za-z]+$')

        # Examine account before registration
        response = self.call_endpoint('/account/%s' % acc, 'get')
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        del(result['created'])
        del(result['last_login'])
        del(result['uid'])
        expected['id'] = acc
        self.assertEqual(result, expected)

        # Register token, check for backup codes
        response = self.call_endpoint('/auth_totp', 'post', data=dict(
            nonce=nonce, otp_first=otp))
        self.assertEqual(response.status_code, 200, 'post failed message=%s' %
                         response.get_json().get('message'))
        self.assertEqual(len(response.get_json().get('backup_codes')), 6)

        # Confirm registered
        response = self.call_endpoint('/account/%s' % acc, 'get')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json().get('totp'))

        # Confirm double-registration is disallowed
        response = self.call_endpoint('/auth_totp', 'post', data=dict(
            nonce=nonce, otp_first=otp))
        self.assertEqual(response.status_code, 403, 'unexpected message=%s' %
                         response.get_json().get('message'))

    @pytest.mark.slow
    @mock.patch('messaging.send_contact.delay')
    def test_totp_login_with_backup(self, mock_messaging):
        """Register a token, verify otp login and backup code login"""

        account = dict(name='IT Flunkie', username='underpaid',
                       identity='underpaid@example.com')
        password = dict(new_password='a0a5bcd-x', verify_password='a0a5bcd-x')

        response = self.call_endpoint('/account', 'post', data=account)
        self.assertEqual(response.status_code, 201)
        uid = response.get_json()['uid']

        for call in mock_messaging.call_args_list:
            password['reset_token'] = call.kwargs.get('token')
        response = self.call_endpoint(
            '/account_password/%s' % uid, 'put', data=password)
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))
        self.authorize(username=account['username'],
                       password=password['new_password'], new_session=True)

        response = self.call_endpoint('/auth_totp', 'get')
        result = response.get_json()
        self.assertEqual(response.status_code, 200)

        # Register token
        response = self.call_endpoint('/auth_totp', 'post', data=dict(
            nonce=result.get('jti'),
            otp_first=pyotp.TOTP(result.get('totp')).now()))
        self.assertEqual(response.status_code, 200, 'post failed message=%s' %
                         response.get_json().get('message'))
        code = response.get_json().get('backup_codes')[3]

        self.authorize(username=account['username'],
                       password=password['new_password'], new_session=True)
        # Confirm session doesn't yet have permission to fetch resources
        response = self.call_endpoint('/credential?filter={"uid":"%s"}' % uid,
                                      'get')
        self.assertEqual(response.status_code, 403, 'unexpected message=%s' %
                         response.get_json().get('message'))
        self.authorize(username=account['username'],
                       otp=pyotp.TOTP(result.get('totp')).now())
        # Now have permissions
        response = self.call_endpoint('/credential?filter={"uid":"%s"}' % uid,
                                      'get')
        self.assertEqual(response.status_code, 200)
        self.assertIn('__Secure-totp', self.flask.cookie_jar._cookies[
            'localhost.local']['/api/v1/auth'].keys())

        # Reauth, without OTP -- using bypass cookie
        self.authorize(username=account['username'],
                       password=password['new_password'], new_session=True)
        response = self.call_endpoint('/credential?filter={"uid":"%s"}' % uid,
                                      'get')
        self.assertEqual(response.status_code, 200)

        # Clear cookie and auth with backup code
        self.flask.cookie_jar._cookies.clear()
        self.authorize(username=account['username'],
                       password=password['new_password'], new_session=True)
        response = self.call_endpoint('/credential?filter={"uid":"%s"}' % uid,
                                      'get')
        self.assertEqual(response.status_code, 403)
        self.authorize(username=account['username'], otp=code)
        response = self.call_endpoint('/credential?filter={"uid":"%s"}' % uid,
                                      'get')
        self.assertEqual(response.status_code, 200)

        # Repeat with bad backup code
        self.flask.cookie_jar._cookies.clear()
        self.authorize(username=account['username'],
                       password=password['new_password'], new_session=True)
        response = self.call_endpoint('/credential?filter={"uid":"%s"}' % uid,
                                      'get')
        self.assertEqual(response.status_code, 403)
        self.authorize(username=account['username'], otp='8digits8')
        response = self.call_endpoint('/credential?filter={"uid":"%s"}' % uid,
                                      'get')
        self.assertEqual(response.status_code, 403)

    @mock.patch('messaging.send_contact.delay')
    def test_totp_failures(self, mock_messaging):
        account = dict(name='Rodney Danger', username='danger23',
                       identity='danger23@example.com')
        password = dict(new_password='a0M5bNdvx', verify_password='a0M5bNdvx')

        response = self.call_endpoint('/account', 'post', data=account)
        self.assertEqual(response.status_code, 201)
        acc = response.get_json()['id']
        uid = response.get_json()['uid']

        for call in mock_messaging.call_args_list:
            password['reset_token'] = call.kwargs.get('token')
        response = self.call_endpoint(
            '/account_password/%s' % uid, 'put', data=password)
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))
        self.authorize(username=account['username'],
                       password=password['new_password'], new_session=True)

        # Try to register a token using invalid nonce
        response = self.call_endpoint('/auth_totp', 'post', dict(
            nonce='invalid', otp_first='654321'))
        self.assertEqual(response.status_code, 403, 'register unexpected')

        # Try to register using invalid otp
        response = self.call_endpoint('/auth_totp', 'get')
        result = response.get_json()
        self.assertEqual(response.status_code, 200)
        nonce = result['jti']
        otp = pyotp.TOTP(result['totp']).now()
        response = self.call_endpoint('/auth_totp', 'post', dict(
            nonce=nonce, otp_first=str(int(otp) ^ 0xffff)))
        self.assertEqual(response.status_code, 403, 'register unexpected')

        # Try to generate a token for an account already registered
        db_session = database.get_session(db_url=self.config.DB_URL)
        account = db_session.query(Account).filter_by(id=acc).one()
        account.totp_secret = pyotp.random_base32()
        db_session.commit()
        db_session.remove()
        response = self.call_endpoint('/auth_totp', 'get')
        self.assertEqual(response.status_code, 403, 'generate unexpected')
