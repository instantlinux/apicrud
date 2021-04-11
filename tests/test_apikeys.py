"""test_apikeys

Tests for apikeys controller

created 27-dec-2020 by richb@instantlinux.net
"""

from datetime import datetime, timedelta

import pytest
from unittest import mock

import test_base


class TestAPIkeys(test_base.TestBase):

    def setUp(self):
        self.authorize()

    def test_add_and_fetch_apikey(self):
        record = dict(name='Test1', uid=self.test_uid, scopes=[self.scope_id])
        expected = dict(
            expires=None, last_used=None,
            owner=self.test_person_name, rbac='dru', status='active', **record)
        response = self.call_endpoint('/apikey', 'post', data=record)
        self.assertEqual(response.status_code, 201, response.get_json().get(
            'message'))
        self.assertEqual(len(response.get_json()['apikey']), 41)
        id = response.get_json()['id']
        response = self.call_endpoint('/apikey/%s' % id, 'get')
        result = response.get_json()
        del(result['created'])
        del(result['prefix'])
        expected['id'] = id
        self.assertEqual(result, expected)

    def test_update_apikey(self):
        record = dict(name='Test2', uid=self.test_uid)
        expected = dict(
            scopes=[], expires=None, last_used=None,
            owner=self.test_person_name, rbac='dru', status='active', **record)
        updated = dict(name='Updated')

        response = self.call_endpoint('/apikey', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/apikey/%s' % id, 'put', data=dict(
            record, **updated))
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))
        response = self.call_endpoint('/apikey/%s' % id, 'get')
        result = response.get_json()
        del(result['created'])
        del(result['modified'])
        del(result['prefix'])
        expected.update(updated)
        expected['id'] = id
        self.assertEqual(result, expected)

        response = self.call_endpoint('/apikey/%s' % id, 'put',
                                      dict(scopes=[self.scope_id], **record))
        self.assertEqual(response.status_code, 200)
        response = self.call_endpoint('/apikey/%s' % id, 'put',
                                      dict(scopes=[], **record))
        self.assertEqual(response.status_code, 200)

    def test_apikey_delete(self):
        record = dict(name='badkey', uid=self.test_uid)

        response = self.call_endpoint('/apikey', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/apikey/%s' % id, 'delete')
        self.assertEqual(response.status_code, 204)

        # Delete is forced -- should no longer exist
        response = self.call_endpoint('/apikey/%s' % id, 'get')
        result = response.get_json()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(result, dict(id=id, message='not found'))

    def test_find_invalid_apikey(self):
        response = self.call_endpoint('/apikey?filter={"name":"invalid"}',
                                      'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), dict(items=[], count=0))
        response = self.call_endpoint('/apikey/invalid', 'get')
        self.assertEqual(response.status_code, 400)

    @mock.patch('logging.info')
    def test_use_invalid_apikey(self, mock_logging):
        bad_key = 'deadbeef.01234567890123456789012345678901'
        bad_key2 = 'tooshort_abc'
        ret = self.authorize(apikey=bad_key)
        self.assertEqual(ret, 401)
        mock_logging.assert_called_with(dict(
            action='api_key', key_id='deadbeef', message='not found'))

        ret = self.authorize(apikey=bad_key2)
        self.assertEqual(ret, 401)

    @pytest.mark.slow
    @mock.patch('messaging.send_contact.delay')
    def test_add_too_many_apikeys(self, mock_messaging):
        max_apikeys = self.config.DEFAULT_GRANTS.get('apikeys')
        account = dict(
            name='Francis Scott Key', username='fskey',
            identity='fskey@conclave.events')
        password = dict(new_password='5db7f#483', verify_password='5db7f#483')

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

        response = self.call_endpoint('/grant?filter={"name":"apikeys"}',
                                      'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['items'], [dict(
            id='%s:apikeys' % uid, name='apikeys', value='2', uid=uid,
            rbac='r', status='active')])

        for i in range(max_apikeys):
            response = self.call_endpoint('/apikey', 'post', data=dict(
                name='key-%d' % i, uid=uid))
            self.assertEqual(response.status_code, 201, 'post message=%s' %
                             response.get_json().get('message'))
        response = self.call_endpoint('/apikey', 'post', data=dict(
            name='key-%d' % max_apikeys, uid=uid))
        self.assertEqual(response.status_code, 405, 'status %d unexpected, '
                         'message=%s' % (response.status_code,
                                         response.get_json().get('message')))
        self.assertEqual(response.get_json(), dict(
            message=u'user limit exceeded', allowed=max_apikeys))

    def test_get_apikey_restricted(self):
        """Attempt to fetch apikey from admin user
        """
        self.authorize(username=self.admin_name, password=self.admin_pw)
        response = self.call_endpoint('/apikey', 'post', data=dict(
            name='adm', uid=self.admin_uid))
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']

        self.authorize(username=self.username, password=self.password)
        expected = dict(message='access denied', id=id)
        response = self.call_endpoint('/apikey/%s' % id, 'get')
        self.assertEqual(response.status_code, 403, 'get failed message=%s' %
                         response.get_json().get('message'))
        result = response.get_json()
        self.assertEqual(result, expected)

    def test_create_not_allowed_other_user(self):
        person = dict(name='Jimmy Tang', identity='jtang@conclave.events')
        record = dict(
            carrier=None, label='home', type='email', privacy='invitee')

        response = self.call_endpoint('/person', 'post', data=person)
        self.assertEqual(response.status_code, 201)
        uid = response.get_json()['id']
        response = self.call_endpoint('/apikey', 'post', data=dict(
                name='impersonator', uid=uid, **record))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json(), dict(message='access denied'))

    @mock.patch('messaging.send_contact.delay')
    def test_apikey_create_and_invoke(self, mock_messaging):
        account = dict(name='Script Kiddie', username='skid',
                       identity='skid@conclave.events')
        expected = dict(
            is_admin=False, name=account['username'], owner=account['name'],
            password_must_change=False, rbac='dru', status='active',
            totp=False, settings_id=self.settings_id)
        password = dict(new_password='0d9bcd-2', verify_password='0d9bcd-2')

        response = self.call_endpoint('/account', 'post', data=account)
        self.assertEqual(response.status_code, 201)
        acc = response.get_json()['id']
        uid = response.get_json()['uid']
        record = dict(name='Test2', uid=uid, scopes=[self.scope_id])

        for call in mock_messaging.call_args_list:
            password['reset_token'] = call.kwargs.get('token')
        response = self.call_endpoint(
            '/account_password/%s' % uid, 'put', data=password)
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))
        self.authorize(username=account['username'],
                       password=password['new_password'], new_session=True)

        response = self.call_endpoint('/apikey', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        new_key = response.get_json()['apikey']
        self.assertEqual(len(new_key), 41)
        response = self.call_endpoint('/apikey/%s' % id, 'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['last_used'], None)
        response = self.call_endpoint('/logout', 'get')
        self.assertEqual(response.status_code, 200, 'get failed message=%s' %
                         response.get_json().get('message'))

        ret = self.authorize(apikey=new_key)
        self.assertEqual(ret, 200, 'APIkey failed')
        response = self.call_endpoint('/account/%s' % acc, 'get')
        self.assertEqual(response.status_code, 200, 'get failed message=%s' %
                         response.get_json().get('message'))
        result = response.get_json()
        del(result['created'])
        del(result['last_login'])
        expected['id'] = acc
        expected['uid'] = uid
        self.assertEqual(result, expected)

        response = self.call_endpoint('/apikey/%s' % id, 'get')
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get_json()['last_used'], None)

    @pytest.mark.slow
    @mock.patch('logging.info')
    @mock.patch('messaging.send_contact.delay')
    def test_expired_apikey(self, mock_messaging, mock_logging):
        account = dict(name='Uncompliant Dev', username='dev1',
                       identity='dev1@conclave.events')
        password = dict(new_password='455#8b76', verify_password='455#8b76')

        response = self.call_endpoint('/account', 'post', data=account)
        self.assertEqual(response.status_code, 201)
        uid = response.get_json()['uid']
        record = dict(
            name='KeyExp1', uid=uid, scopes=[self.scope_id],
            expires=(datetime.utcnow() - timedelta(hours=1)).strftime(
                '%Y-%m-%dT%H:%M:%SZ'))

        for call in mock_messaging.call_args_list:
            password['reset_token'] = call.kwargs.get('token')
        response = self.call_endpoint(
            '/account_password/%s' % uid, 'put', data=password)
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))
        self.authorize(username=account['username'],
                       password=password['new_password'], new_session=True)

        response = self.call_endpoint('/apikey', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        new_key = response.get_json()['apikey']
        self.assertEqual(len(new_key), 41)
        response = self.call_endpoint('/logout', 'get')
        self.assertEqual(response.status_code, 200)

        ret = self.authorize(apikey=new_key)
        self.assertEqual(ret, 401)
        mock_logging.assert_called_with(dict(
            action='api_key', key_id=new_key[:8], uid=uid, message='expired'))
