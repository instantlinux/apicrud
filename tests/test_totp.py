"""test_totp

Tests for auth TOTP

created 6-apr-2021 by richb@instantlinux.net
"""

import jwt
import pyotp
import pytest

import test_base

from apicrud import database
from example.models import Account


class TestAuthTOTP(test_base.TestBase):
    def test_totp_generate_reg(self):
        """Generate and register a token"""

        expected = dict(
            is_admin=False, name='theboss', owner='IT Admin',
            password_must_change=False, rbac='dru', status='active',
            totp=False, settings_id=self.settings_id)

        with self.scratch_account(expected['name'], expected['owner']) as acc:
            response = self.call_endpoint('/auth_totp', 'get')
            result = response.get_json()
            self.assertEqual(response.status_code, 200)
            nonce = result['jti']
            otp = pyotp.TOTP(result['totp']).now()
            self.assertEqual(result['auth'], 'pendingtotp')
            self.assertRegex(result['uri'],
                             '^otpauth://totp/[A-Za-z]+:theboss%40example.com'
                             '[?]+secret=[A-Z0-9]{32}&issuer=[A-Za-z]+$')

            # Examine account before registration
            response = self.call_endpoint('/account/%s' % acc.id, 'get')
            self.assertEqual(response.status_code, 200)
            result = response.get_json()
            del result['created']
            del result['last_login']
            del result['uid']
            expected['id'] = acc.id
            self.assertEqual(result, expected)

            # Register token, check for backup codes
            response = self.call_endpoint('/auth_totp', 'post', data=dict(
                nonce=nonce, otp_first=otp))
            self.assertEqual(
                response.status_code, 200, 'post failed message=%s' %
                response.get_json().get('message'))
            self.assertEqual(len(response.get_json().get('backup_codes')), 6)

            # Confirm registered
            response = self.call_endpoint('/account/%s' % acc.id, 'get')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.get_json().get('totp'))

            # Confirm double-registration is disallowed
            response = self.call_endpoint('/auth_totp', 'post', data=dict(
                nonce=nonce, otp_first=otp))
            self.assertEqual(
                response.status_code, 403, 'unexpected message=%s' %
                response.get_json().get('message'))

    @pytest.mark.slow
    def test_totp_login_with_backup(self):
        """Register a token, verify otp login and backup code login"""

        username = 'underpaid'
        with self.scratch_account(username, 'IT Flunkie') as acc:
            response = self.call_endpoint('/auth_totp', 'get')
            result = response.get_json()
            self.assertEqual(response.status_code, 200)

            # Register token
            response = self.call_endpoint('/auth_totp', 'post', data=dict(
                nonce=result.get('jti'),
                otp_first=pyotp.TOTP(result.get('totp')).now()))
            self.assertEqual(
                response.status_code, 200, 'post failed message=%s' %
                response.get_json().get('message'))
            code = response.get_json().get('backup_codes')[3]

            self.authorize(username=username, password=acc.password,
                           new_session=True)
            # Confirm session doesn't yet have permission to fetch resources
            response = self.call_endpoint(
                '/credential?filter={"uid":"%s"}' % acc.uid, 'get')
            self.assertEqual(
                response.status_code, 403, 'unexpected message=%s' %
                response.get_json().get('message'))
            self.authorize(username=username,
                           otp=pyotp.TOTP(result.get('totp')).now())
            # Now have permissions
            response = self.call_endpoint(
                '/credential?filter={"uid":"%s"}' % acc.uid, 'get')
            self.assertEqual(response.status_code, 200)
            self.assertIn('__Secure-totp', self.flask.cookie_jar._cookies[
                'localhost.local']['/api/v1/auth'].keys())

            # Reauth, without OTP -- using bypass cookie
            self.authorize(username=username, password=acc.password,
                           new_session=True)
            response = self.call_endpoint(
                '/credential?filter={"uid":"%s"}' % acc.uid, 'get')
            self.assertEqual(response.status_code, 200)

            # Clear cookie and auth with backup code
            self.flask.cookie_jar._cookies.clear()
            self.authorize(username=username, password=acc.password,
                           new_session=True)
            response = self.call_endpoint(
                '/credential?filter={"uid":"%s"}' % acc.uid, 'get')
            self.assertEqual(response.status_code, 403)
            self.authorize(username=username, otp=code)
            response = self.call_endpoint(
                '/credential?filter={"uid":"%s"}' % acc.uid, 'get')
            self.assertEqual(response.status_code, 200)

            # Repeat with bad backup code
            self.flask.cookie_jar._cookies.clear()
            self.authorize(username=username, password=acc.password,
                           new_session=True)
            response = self.call_endpoint(
                '/credential?filter={"uid":"%s"}' % acc.uid, 'get')
            self.assertEqual(response.status_code, 403)
            self.authorize(username=username, otp='8digits8')
            response = self.call_endpoint(
                '/credential?filter={"uid":"%s"}' % acc.uid, 'get')
            self.assertEqual(response.status_code, 403)

    def test_totp_failures(self):
        with self.scratch_account('danger23', 'Rodney Danger'):
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
                nonce=nonce, otp_first=str(int(otp) ^ 0xffff).zfill(6)))
            self.assertEqual(response.status_code, 403, 'register unexpected')

            response = self.call_endpoint('/auth_params', 'get')
            self.assertEqual(response.status_code, 200)

            # Try to generate a token for an account already registered
            db_session = database.get_session(db_url=self.config.DB_URL)
            account = db_session.query(Account).filter_by(
                id=response.get_json()['account_id']).one()
            account.totp_secret = pyotp.random_base32()
            db_session.commit()
            db_session.remove()
            response = self.call_endpoint('/auth_totp', 'get')
            self.assertEqual(response.status_code, 403, 'generate unexpected')

    def test_totp_required(self):
        with self.scratch_account('gcote123', 'Greg Cote') as acc:
            with self.config_overrides(login_mfa_required=True):
                response = self.call_endpoint('/auth', 'post', data=dict(
                    username='gcote123', password=acc.password))
                self.assertEqual(response.status_code, 201)
                tok = jwt.decode(response.get_json()['jwt_token'],
                                 self.config.JWT_SECRET, algorithms=['HS256'])
                self.assertEqual(tok['auth'], 'mfarequired')
