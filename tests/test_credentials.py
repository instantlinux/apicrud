"""test_credentials

Tests for credentials controller

created 22-aug-2020 by richb@instantlinux.net
"""

from datetime import datetime, timedelta

import test_base


class TestCredentials(test_base.TestBase):

    def setUp(self):
        self.authorize()

    def test_add_and_fetch_credential(self):
        record = dict(name='cred1', vendor='google', uid=self.test_uid,
                      secret='wellkept', settings_id=self.settings_id)
        expected = dict(
            type=None, url=None, key=None, expires=None,
            owner=self.test_person_name, rbac='dru', status='active', **record)
        response = self.call_endpoint('/credential', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/credential/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        del expected['secret']
        expected['id'] = id
        self.assertEqual(result, expected)

    def test_update_credential(self):
        record = dict(name='newcred1', vendor='google', uid=self.test_uid,
                      secret='passowrd', settings_id=self.settings_id)
        expected = dict(
            type=None, url=None, key=None, expires=None,
            owner=self.test_person_name, rbac='dru', status='active', **record)
        updated = dict(secret='leaked')

        response = self.call_endpoint('/credential', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/credential/%s' % id, 'put', data=dict(
            record, **updated))
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))
        response = self.call_endpoint('/credential/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        del result['modified']
        expected.update(updated)
        del expected['secret']
        expected['id'] = id
        self.assertEqual(result, expected)

    def test_credential_delete(self):
        record = dict(name='badcredit', vendor='aws', uid=self.test_uid,
                      secret='mywife', settings_id=self.settings_id)
        expected = dict(
            type=None, url=None, key=None, expires=None, rbac='dru',
            owner=self.test_person_name, status='disabled', **record)

        response = self.call_endpoint('/credential', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/credential/%s' % id, 'delete')
        self.assertEqual(response.status_code, 204)

        # The record should still exist, with disabled status
        response = self.call_endpoint('/credential/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        del expected['secret']
        expected['id'] = id

        self.assertEqual(result, expected)

        # Force delete -- should no longer exist
        response = self.call_endpoint('/credential/%s?force=true' % id,
                                      'delete')
        self.assertEqual(response.status_code, 204)
        response = self.call_endpoint('/credential/%s' % id, 'get')
        result = response.get_json()
        self.assertEqual(response.status_code, 404)

    def test_invalid_credential(self):
        response = self.call_endpoint('/credential?filter={"name":"invalid"}',
                                      'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), dict(items=[], count=0))
        response = self.call_endpoint('/credential/invalid', 'get')
        self.assertEqual(response.status_code, 400)

    def test_get_expired_credential(self):
        record = dict(name='stale1', vendor='google', uid=self.test_uid,
                      settings_id=self.settings_id,
                      secret='mygrandmasbirthday', expires=(
                          datetime.utcnow() - timedelta(hours=1)).strftime(
                              '%Y-%m-%dT%H:%M:%SZ'))
        expected = dict(
            type=None, url=None, key=None,
            owner=self.test_person_name, rbac='dru', status='active', **record)

        response = self.call_endpoint('/credential', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/credential/%s' % id, 'get')
        result = response.get_json()
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        del result['created']
        del expected['secret']
        expected['id'] = id
        self.assertEqual(result, expected)
