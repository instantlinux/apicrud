"""test_grants

Tests for grants controller

created 8-nov-2019 by richb@instantlinux.net
"""

from datetime import datetime, timedelta
from flask import g

import test_base

from apicrud import database, Grants


class TestGrants(test_base.TestBase):

    def setUp(self):
        self.authorize(username=self.admin_name, password=self.admin_pw)

    def test_add_and_fetch_grant(self):
        record = dict(name='contacts', value='4', uid=self.test_uid)
        expected = dict(
            expires=None, owner=self.test_person_name,
            rbac='dru', status='active', **record)
        response = self.call_endpoint('/grant', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/grant/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        expected['id'] = id
        self.assertEqual(result, expected)

        with self.app.test_request_context():
            g.db = database.get_session()
            self.assertEqual(Grants().get(
                record['name'], uid=self.test_uid), int(record['value']))
            g.db.remove()

        # Clean up the grant
        response = self.call_endpoint('/grant/%s' % id, 'delete')
        self.assertEqual(response.status_code, 204)

    def test_get_multiple_grants(self):
        person = dict(name='Ulysses Grant III', identity='grant3@aol.com')
        record = dict(name='lists', value='12')

        response = self.call_endpoint('/person', 'post', data=person)
        self.assertEqual(response.status_code, 201)
        record['uid'] = response.get_json()['id']

        # Update a single grant
        response = self.call_endpoint(
            '/grant/%s:%s' % (record['uid'], record['name']), 'put',
            data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/grant/%s' % id, 'get')
        self.assertEqual(response.status_code, 200)
        updated = response.get_json()
        updated['modified'] = None

        expected = dict(
            items=[
                dict(id='%s:%s' % (record['uid'], k), name=k, value=str(v),
                     uid=record['uid'], rbac='cdru', status='active')
                for k, v in self.config.DEFAULT_GRANTS.items()],
            count=len(self.config.DEFAULT_GRANTS))
        # Confirm that updated grant is no longer default value
        expected['items'][list(self.config.DEFAULT_GRANTS.keys()).index(
            record['name'])] = updated

        response = self.call_endpoint('/grant?filter={"uid":"%s"}' %
                                      record['uid'], 'get')
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result, expected)

        # Apply name filter and verify
        response = self.call_endpoint('/grant?filter={"uid":"%s","name":"%s"}'
                                      % (record['uid'], record['name']), 'get')
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result, dict(items=[updated], count=1))

    def test_update_grant(self):
        record = dict(name='list_size', value='300', uid=self.test_uid)
        updated = dict(value='500')
        expected = dict(
            expires=None, owner=self.test_person_name,
            rbac='dru', status='active', **record)

        response = self.call_endpoint('/grant', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/grant/%s' % id, 'put', data=dict(
            record, **updated))
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))
        response = self.call_endpoint('/grant/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        del result['modified']
        expected.update(updated)
        expected['id'] = id
        self.assertEqual(result, expected)

    def test_grant_delete(self):
        record = dict(name='list_size', value="100", uid=self.test_uid)
        expected = dict(
            expires=None, owner=self.test_person_name,
            rbac='dru', status='disabled', **record)

        response = self.call_endpoint('/grant', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/grant/%s' % id, 'delete')
        self.assertEqual(response.status_code, 204)

        # The record should still exist, with disabled status
        response = self.call_endpoint('/grant/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        expected['id'] = id

        self.assertEqual(result, expected)

        # Force delete -- should no longer exist
        response = self.call_endpoint('/grant/%s?force=true' % id, 'delete')
        self.assertEqual(response.status_code, 204)
        response = self.call_endpoint('/grant/%s' % id, 'get')
        result = response.get_json()
        self.assertEqual(response.status_code, 404)

    def test_default_grant(self):
        expected = dict(
            id='%s:%s' % (self.test_uid, 'list_size'), name='list_size',
            uid=self.test_uid, value='250', rbac='cdru', status='active')

        response = self.call_endpoint('/grant/%s:%s' %
                                      (self.test_uid, expected['name']), 'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), expected)

    def test_invalid_grant(self):
        response = self.call_endpoint('/grant?name=invalid', 'get')
        self.assertEqual(response.status_code, 400)

        with self.app.test_request_context():
            g.db = database.get_session()
            self.assertIsNone(Grants().get('invalid'))

    def test_get_expired_grant(self):
        record = dict(name='lists', value="20", uid=self.test_uid, expires=(
            datetime.utcnow() - timedelta(hours=1)).strftime(
                '%Y-%m-%dT%H:%M:%SZ'))
        expected = dict(
            owner=self.test_person_name, rbac='dru', status='active', **record)

        with self.app.test_request_context():
            g.db = database.get_session()

            self.assertEqual(
                int(Grants().get(record['name'], uid=self.test_uid)),
                self.config.DEFAULT_GRANTS[record['name']])

            response = self.call_endpoint('/grant', 'post', data=record)
            self.assertEqual(response.status_code, 201)
            id = response.get_json()['id']
            response = self.call_endpoint('/grant/%s' % id, 'get')
            self.assertEqual(response.status_code, 200)
            result = response.get_json()
            del result['created']
            expected['id'] = id
            self.assertEqual(result, expected)

            self.assertEqual(
                Grants().get(record['name'], uid=self.test_uid),
                self.config.DEFAULT_GRANTS[record['name']])
            g.db.remove()

        # Clean up the grant
        response = self.call_endpoint('/grant/%s' % id, 'delete')
        self.assertEqual(response.status_code, 204)
