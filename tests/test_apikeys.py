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
        del result['created']
        del result['prefix']
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
        del result['created']
        del result['modified']
        del result['prefix']
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
        response = self.call_endpoint('/apikey/%s?force=true' % id, 'delete')
        self.assertEqual(response.status_code, 204)

        # Delete-force -- should no longer exist
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
        self.assertEqual(ret, 403)
        # TODO: figure out why this used to work
        # mock_logging.assert_called_with(dict(
        #     action='api_key', key_id='deadbeef', message='not found'))

        ret = self.authorize(apikey=bad_key2)
        self.assertEqual(ret, 403)

    @pytest.mark.slow
    def test_add_too_many_apikeys(self):
        max_apikeys = self.config.DEFAULT_GRANTS.get('apikeys')

        with self.scratch_account('fskey', 'Francis Scott Key') as acc:
            response = self.call_endpoint('/grant?filter={"name":"apikeys"}',
                                          'get')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['items'], [dict(
                id='%s:apikeys' % acc.uid, name='apikeys', value='2',
                uid=acc.uid, rbac='r', status='active')])

            for i in range(max_apikeys):
                response = self.call_endpoint('/apikey', 'post', data=dict(
                    name='key-%d' % i, uid=acc.uid))
                self.assertEqual(response.status_code, 201, 'post message=%s' %
                                 response.get_json().get('message'))
            response = self.call_endpoint('/apikey', 'post', data=dict(
                name='key-%d' % max_apikeys, uid=acc.uid))
            self.assertEqual(
                response.status_code, 405, 'status %d unexpected, '
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

    def test_apikey_create_and_invoke(self):
        expected = dict(
            is_admin=False, name='skid', owner='Script Kiddie',
            password_must_change=False, rbac='dru', status='active',
            totp=False, settings_id=self.settings_id)

        with self.scratch_account(expected['name'], expected['owner']) as acc:
            record = dict(name='Test2', uid=acc.uid, scopes=[self.scope_id])
            response = self.call_endpoint('/apikey', 'post', data=record)
            self.assertEqual(response.status_code, 201)
            id = response.get_json()['id']
            new_key = response.get_json()['apikey']
            self.assertEqual(len(new_key), 41)
            response = self.call_endpoint('/apikey/%s' % id, 'get')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['last_used'], None)
            response = self.call_endpoint('/logout', 'get')
            self.assertEqual(
                response.status_code, 200, 'get failed message=%s' %
                response.get_json().get('message'))

            ret = self.authorize(apikey=new_key)
            self.assertEqual(ret, 200, 'APIkey failed')
            response = self.call_endpoint('/account/%s' % acc.id, 'get')
            self.assertEqual(
                response.status_code, 200, 'get failed message=%s' %
                response.get_json().get('message'))
            result = response.get_json()
            del result['created']
            del result['last_login']
            expected['id'] = acc.id
            expected['uid'] = acc.uid
            self.assertEqual(result, expected)

            response = self.call_endpoint('/apikey/%s' % id, 'get')
            self.assertEqual(response.status_code, 200)
            self.assertNotEqual(response.get_json()['last_used'], None)

    @pytest.mark.slow
    @mock.patch('logging.info')
    @mock.patch('logging.error')
    def test_expired_apikey(self, mock_error, mock_logging):
        with self.scratch_account('dev1', 'Uncompliant Dev') as acc:
            record = dict(
                name='KeyExp1', uid=acc.uid, scopes=[self.scope_id],
                expires=(datetime.utcnow() - timedelta(hours=1)).strftime(
                    '%Y-%m-%dT%H:%M:%SZ'))

            response = self.call_endpoint('/apikey', 'post', data=record)
            self.assertEqual(response.status_code, 201)
            new_key = response.get_json()['apikey']
            self.assertEqual(len(new_key), 41)
            response = self.call_endpoint('/logout', 'get')
            self.assertEqual(response.status_code, 200)

            mock_logging.reset_mock()
            ret = self.authorize(apikey=new_key)
            self.assertEqual(ret, 401)
            mock_logging.assert_has_calls([
                mock.call(dict(action='api_key', key_id=new_key[:8],
                               uid=acc.uid, message='expired')),
                mock.call('action=logout username=%s token_auth=missing' %
                          acc.uid)
            ])
