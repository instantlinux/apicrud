"""test_accounts

Tests for accounts controller

created 4-nov-2019 by richb@instantlinux.net
"""

import mock
import pytest

from apicrud import database
from models import Profile

import test_base


class TestAccounts(test_base.TestBase):

    @pytest.mark.slow
    @mock.patch('messaging.send_contact.delay')
    def test_add_and_fetch_account(self, mock_messaging):
        record = dict(
            name='Jessica Simpson',
            identity='mylittlepony@conclave.events', username='littlepony')
        password = dict(
            new_password='g1rlzluvHorses', verify_password='g1rlzluvHorses')
        expected = dict(
            password_must_change=False, is_admin=False, last_login=None,
            name=record['username'], rbac='dru', owner=record['name'],
            settings_id=self.settings_id, status='active')

        response = self.call_endpoint('/account', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        uid = response.get_json()['uid']

        for call in mock_messaging.call_args_list:
            password['reset_token'] = call.kwargs.get('token')
        response = self.call_endpoint(
            '/account_password/%s' % uid, 'put', data=password)
        self.assertEqual(response.status_code, 200)

        self.authorize(username=self.admin_name, password=self.admin_pw)
        response = self.call_endpoint('/account/%s' % id, 'get')
        self.assertEqual(response.status_code, 200, 'get failed message=%s' %
                         response.get_json().get('message'))
        result = response.get_json()
        del(result['created'])
        del(result['uid'])
        expected['id'] = id
        self.assertEqual(result, expected)

    @mock.patch('messaging.send_contact.delay')
    def test_register_and_login(self, mock_messaging):
        record = dict(
            name='Black Hat', identity='blackhat@ddos.net', username='devil')
        password = dict(
            new_password='GOPdem!2020', verify_password='GOPdem!2020')
        expected = dict(
            identity=record['identity'], lists=[],
            name=record['name'], privacy='public', rbac='dru',
            referrer_id=None, status='active')

        response = self.call_endpoint('/account', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        uid = response.get_json()['uid']

        # Verify still unauthorized
        response = self.call_endpoint('/person/%s' % uid, 'get')
        self.assertEqual(response.status_code, 401, 'get unexpected message=%s'
                         % response.get_json().get('message'))

        mock_messaging.assert_has_calls([
            mock.call(to=mock.ANY, template='confirm_new', token=mock.ANY,
                      type='email')])
        for call in mock_messaging.call_args_list:
            password['reset_token'] = call.kwargs.get('token')

        # Set the password with put, and confirm it's present with get
        response = self.call_endpoint(
            '/account_password/%s' % uid, 'put', data=password)
        self.assertEqual(response.status_code, 200, 'put failed message=%s'
                         % response.get_json().get('message'))
        response = self.call_endpoint(
            '/account_password/%s' % uid, 'get', data=password)
        self.assertEqual(response.status_code, 200, 'get failed message=%s'
                         % response.get_json().get('message'))
        self.assertEqual(response.get_json(), dict(
            id=uid, username=record['username']))

        # Also test an invalid account uid
        response = self.call_endpoint(
            '/account_password/%s' % 'x-invalid1', 'get', data=password)
        self.assertEqual(response.status_code, 404, 'unexpected message=%s'
                         % response.get_json().get('message'))

        # Authorize and fetch own record
        self.authorize(username=record['username'],
                       password=password['new_password'])
        response = self.call_endpoint('/person/%s' % uid, 'get')
        self.assertEqual(response.status_code, 200, 'get failed message=%s' %
                         response.get_json().get('message'))
        result = response.get_json()
        del(result['created'])
        expected['id'] = uid
        self.assertEqual(result, expected)

    @mock.patch('messaging.send_contact.delay')
    def test_get_account_lang_es(self, mock_messaging):
        expected = dict(id=self.adm_contact_2, message=u'acceso denegado')

        record = dict(
            name='Guillermo Morales', identity='gm@sistema.es',
            username='diablocachondo')
        password = dict(
            new_password='6.1480j0', verify_password='6.1480j0')

        response = self.call_endpoint('/account', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        uid = response.get_json()['uid']

        for call in mock_messaging.call_args_list:
            password['reset_token'] = call.kwargs.get('token')

        # Set the password with put, and confirm it's present with get
        response = self.call_endpoint(
            '/account_password/%s' % uid, 'put', data=password)
        self.assertEqual(response.status_code, 200, 'put failed message=%s'
                         % response.get_json().get('message'))
        response = self.call_endpoint(
            '/account_password/%s' % uid, 'get', data=password)
        self.assertEqual(response.status_code, 200, 'get failed message=%s'
                         % response.get_json().get('message'))
        # Set lang profile
        db_session = database.get_session(db_url=self.config.DB_URL)
        db_session.add(Profile(id='x-fb3M81e7', uid=uid, item='lang',
                               value='es_ES', status='active'))
        db_session.commit()
        db_session.remove()
        self.authorize(username=record['username'],
                       password=password['new_password'])
        response = self.call_endpoint(
            '/contact/%s' % self.adm_contact_2, 'get',
            extraheaders={'Accept-Language': 'es_ES'})
        self.assertEqual(response.get_json(), expected)
        self.assertEqual(response.status_code, 403)

    @mock.patch('messaging.send_contact.delay')
    def test_register_existing_person(self, mock_messaging):
        person = dict(name='Edgar Rodriguez', identity='edgar@conclave.events')
        username = 'eddie'
        password = dict(
            new_password='jthyu2@JY', verify_password='jthyu2@JY')

        self.authorize()
        response = self.call_endpoint('/person', 'post', data=person)
        self.assertEqual(response.status_code, 201, 'get failed message=%s' %
                         response.get_json().get('message'))
        response = self.call_endpoint('/account', 'post', data=dict(
            username=username, **person))
        self.assertEqual(response.status_code, 201)
        uid = response.get_json()['uid']

        mock_messaging.assert_has_calls([
            mock.call(to=mock.ANY, template='confirm_new', token=mock.ANY,
                      type='email')])
        for call in mock_messaging.call_args_list:
            password['reset_token'] = call.kwargs.get('token')

        # Set the password with put, and confirm it's present with get
        response = self.call_endpoint(
            '/account_password/%s' % uid, 'put', data=password)
        self.assertEqual(response.status_code, 200, 'put failed message=%s'
                         % response.get_json().get('message'))
        response = self.call_endpoint(
            '/account_password/%s' % uid, 'get', data=password)
        self.assertEqual(response.status_code, 200, 'get failed message=%s'
                         % response.get_json().get('message'))
        self.assertEqual(response.get_json(), dict(id=uid, username=username))

    @pytest.mark.slow
    @mock.patch('messaging.send_contact.delay')
    def test_change_password_reset(self, mock_messaging):
        record = dict(
            name='Drunk Fool', identity='fool@aol.com', username='dfool')
        first_pw = 'cC5$#4Hg'
        updated_password = '3DGZH1%y'
        password = dict(new_password=first_pw, verify_password=first_pw)

        response = self.call_endpoint('/account', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        uid = response.get_json()['uid']
        mock_messaging.assert_has_calls([
            mock.call(to=mock.ANY, template='confirm_new', token=mock.ANY,
                      type='email')])
        for call in mock_messaging.call_args_list:
            password['reset_token'] = call.kwargs.get('token')

        response = self.call_endpoint(
            '/account_password/%s' % uid, 'put', data=password)
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))

        # Get new reset token and update
        response = self.call_endpoint('/account', 'post', data=dict(
            forgot_password=True, username=record['username']))
        self.assertEqual(response.status_code, 200, 'post failed message=%s' %
                         response.get_json().get('message'))
        mock_messaging.assert_has_calls([
            mock.call(to=mock.ANY, template='password_reset', token=mock.ANY,
                      type='email')])
        for call in mock_messaging.call_args_list:
            reset_token = call.kwargs.get('token')
        response = self.call_endpoint(
            '/account_password/%s' % uid,
            'put', data=dict(new_password=updated_password,
                             verify_password=updated_password,
                             reset_token=reset_token))
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))

        # Verify old pw no longer works
        response = self.call_endpoint('/logout', 'get')
        self.assertEqual(response.status_code, 200, 'get failed message=%s' %
                         response.get_json().get('message'))
        status = self.authorize(username=record['username'],
                                password=first_pw,
                                new_session=True)
        self.assertEqual(status, 403)

        response = self.call_endpoint('/person/%s' % uid, 'get')
        self.assertEqual(response.status_code, 401, 'get unexpected message=%s'
                         % response.get_json().get('message'))
        # Reauthorize
        self.authorize(username=record['username'],
                       password=updated_password, new_session=True)
        response = self.call_endpoint('/person/%s' % uid, 'get')
        self.assertEqual(response.status_code, 200, 'get failed message=%s' %
                         response.get_json().get('message'))

    @pytest.mark.slow
    @mock.patch('messaging.send_contact.delay')
    def test_change_password_using_old(self, mock_messaging):
        record = dict(
            name='Farah Faucet', identity='farah@baidu.com', username='farah')
        first_pw = 'h4UPgBgx0@O'
        updated_password = 'fh16&Gi!ee'
        password = dict(new_password=first_pw, verify_password=first_pw)

        response = self.call_endpoint('/account', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        uid = response.get_json()['uid']
        for call in mock_messaging.call_args_list:
            password['reset_token'] = call.kwargs.get('token')

        response = self.call_endpoint(
            '/account_password/%s' % uid, 'put', data=password)
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))

        # Try a wrong pw, then the correct one
        response = self.call_endpoint(
            '/account_password/%s' % uid,
            'put', data=dict(old_password='N0Tvalid@',
                             new_password=updated_password,
                             verify_password=updated_password))
        self.assertEqual(response.status_code, 403, 'unexpected message=%s' %
                         response.get_json().get('message'))
        response = self.call_endpoint(
            '/account_password/%s' % uid,
            'put', data=dict(old_password=first_pw,
                             new_password=updated_password,
                             verify_password=updated_password))
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))

        response = self.call_endpoint('/logout', 'get')
        self.assertEqual(response.status_code, 200, 'get failed message=%s' %
                         response.get_json().get('message'))
        response = self.call_endpoint('/person/%s' % uid, 'get')
        self.assertEqual(response.status_code, 401, 'get unexpected message=%s'
                         % response.get_json().get('message'))
        # Reauthorize and confirm fetch self works
        self.authorize(username=record['username'],
                       password=updated_password, new_session=True)
        response = self.call_endpoint('/person/%s' % uid, 'get')
        self.assertEqual(response.status_code, 200, 'get failed message=%s' %
                         response.get_json().get('message'))

    @pytest.mark.slow
    @mock.patch('messaging.send_contact.delay')
    @mock.patch('time.sleep')
    def test_account_lockout(self, mock_sleep, mock_messaging):
        record = dict(
            name='Brute Force', identity='brute@ddos.net', username='brute')
        password = dict(new_password='WorkingPa3s&',
                        verify_password='WorkingPa3s&')

        response = self.call_endpoint('/account', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        uid = response.get_json()['uid']
        for call in mock_messaging.call_args_list:
            password['reset_token'] = call.kwargs.get('token')

        response = self.call_endpoint(
            '/account_password/%s' % uid, 'put', data=password)
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))

        for i in range(self.config.LOGIN_ATTEMPTS_MAX):
            status = self.authorize(username=record['username'],
                                    password='Disallowed',
                                    new_session=True)
            self.assertEqual(status, 403)

        status = self.authorize(username=record['username'],
                                password=password['new_password'],
                                new_session=True)
        self.assertEqual(status, 403)
        mock_sleep.assert_has_calls([mock.call(5)])

    @pytest.mark.slow
    @mock.patch('messaging.send_contact.delay')
    def test_account_disabled(self, mock_messaging):
        record = dict(
            name='Adam Tsui', identity='tsui@conclave.events', username='tsui')
        password = dict(new_password='%4orohOH', verify_password='%4orohOH')

        response = self.call_endpoint('/account', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        uid = response.get_json()['uid']
        for call in mock_messaging.call_args_list:
            password['reset_token'] = call.kwargs.get('token')

        response = self.call_endpoint(
            '/account_password/%s' % uid, 'put', data=password)
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))

        status = self.authorize(username=record['username'],
                                password=password['new_password'])
        self.assertEqual(status, 201)

        self.authorize(username=self.admin_name, password=self.admin_pw)
        response = self.call_endpoint('/account/%s' % id, 'delete')
        self.assertEqual(response.status_code, 204)

        status = self.authorize(username=record['username'],
                                password=password['new_password'],
                                new_session=True)
        self.assertEqual(status, 403)

    @pytest.mark.slow
    @mock.patch('messaging.send_contact.delay')
    def test_account_reset_bad_token(self, mock_messaging):
        record = dict(
            name='Barry Bonds', identity='bonds@ddos.net', username='bonds')
        password = dict(new_password='MyPa3s&=', verify_password='MyPa3s&=')

        response = self.call_endpoint('/account', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        uid = response.get_json()['uid']

        response = self.call_endpoint(
            '/account_password/%s' % uid, 'put', data=dict(
                reset_token='notvalid', **password))
        self.assertEqual(response.status_code, 405, 'unexpected message=%s' %
                         response.get_json().get('message'))
        self.assertEqual(response.get_json(), dict(
            message='invalid token', username=record['username']))

    @mock.patch('messaging.send_contact.delay')
    def test_weak_or_mismatching_password(self, mock_messaging):
        record = dict(
            name='Clueless Luser', identity='luser@aol.com', username='luser')
        password = dict(
            new_password='password123', verify_password='password123')

        response = self.call_endpoint('/account', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        uid = response.get_json()['uid']
        for call in mock_messaging.call_args_list:
            password['reset_token'] = call.kwargs.get('token')

        response = self.call_endpoint(
            '/account_password/%s' % uid, 'put', data=password)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.get_json(),
                         dict(message='rejected weak password'))

        # Get new reset token and update
        response = self.call_endpoint('/account', 'post', data=dict(
            forgot_password=True, identity=record['identity']))
        self.assertEqual(response.status_code, 200, 'post failed message=%s' %
                         response.get_json().get('message'))
        for call in mock_messaging.call_args_list:
            password['reset_token'] = call.kwargs.get('token')

        password['new_password'] = 'Better@pw2'
        response = self.call_endpoint('/account_password/%s' % uid,
                                      'put', data=password)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.get_json(),
                         dict(message='passwords do not match'))

    @mock.patch('messaging.send_contact.delay')
    def test_duplicate_account(self, mock_messaging):
        record = dict(
            name='Yin Yang', identity='twins@cnn.com', username='twins')

        response = self.call_endpoint('/account', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        response = self.call_endpoint('/account', 'post', data=record)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.get_json(),
                         dict(message='that username is already registered'))
        record['username'] = 'gemelos'
        response = self.call_endpoint('/account', 'post', data=record)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.get_json(),
                         dict(message=('that email is already registered,'
                                       ' use forgot-password')))

    def test_ignore_invalid_forgot_pw_request(self):
        response = self.call_endpoint('/account', 'post', data=dict(
            forgot_password=True, username='notavaliduser'))
        self.assertEqual(response.status_code, 404, 'unexpected message=%s' %
                         response.get_json().get('message'))
        self.assertEqual(response.get_json(),
                         dict(message='username or email not found'))
