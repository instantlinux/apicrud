"""test_profile

Tests for profile controller

created 22-aug-2020 by richb@instantlinux.net
"""

import test_base


class TestProfile(test_base.TestBase):

    def setUp(self):
        self.authorize()

    def test_add_and_fetch_profile(self):
        record = dict(item='employer', value='Google', uid=self.test_uid)
        expected = dict(
            owner=self.test_person_name, rbac='dru', status='active',
            location_id=None, tz_id=None, privacy='public', **record)
        response = self.call_endpoint('/profile', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/profile/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        expected['id'] = id
        self.assertEqual(result, expected)

    def test_update_profile(self):
        record = dict(item='jobtitle', value='Program Manager',
                      privacy='member', uid=self.test_uid)
        expected = dict(
            owner=self.test_person_name, rbac='dru', status='active',
            location_id=None, tz_id=None, **record)
        updated = dict(value='Director')

        response = self.call_endpoint('/profile', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/profile/%s' % id, 'put', data=dict(
            record, **updated))
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))
        response = self.call_endpoint('/profile/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        del result['modified']
        expected.update(updated)
        expected['id'] = id
        self.assertEqual(result, expected)

    def test_profile_delete(self):
        record = dict(item='hometown', value='St. Louis', uid=self.test_uid)
        expected = dict(
            owner=self.test_person_name, status='disabled', rbac='dru',
            location_id=None, tz_id=None, privacy='public', **record)

        response = self.call_endpoint('/profile', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/profile/%s' % id, 'delete')
        self.assertEqual(response.status_code, 204)

        # The record should still exist, with disabled status
        response = self.call_endpoint('/profile/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        expected['id'] = id

        self.assertEqual(result, expected)

        # Force delete -- should no longer exist
        response = self.call_endpoint('/profile/%s?force=true' % id,
                                      'delete')
        self.assertEqual(response.status_code, 204)
        response = self.call_endpoint('/profile/%s' % id, 'get')
        result = response.get_json()
        self.assertEqual(response.status_code, 404)

    def test_invalid_profile(self):
        response = self.call_endpoint('/profile?filter={"item":"invalid"}',
                                      'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), dict(items=[], count=0))
        response = self.call_endpoint('/profile/invalid', 'get')
        self.assertEqual(response.status_code, 400)

    def test_invalid_profile_item(self):
        record = dict(item='not-ok', value='anything', uid=self.test_uid)

        response = self.call_endpoint('/profile', 'post', data=record)
        self.assertEqual(response.status_code, 400)
        self.assertIn("'not-ok' is not one of", response.get_json()['message'])

    def test_profile_tz(self):
        record = dict(item='tz', tz_id=619, uid=self.test_uid)
        expected = dict(
            owner=self.test_person_name, rbac='dru', status='active',
            location_id=None, value=None, privacy='public', **record)
        response = self.call_endpoint('/profile', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/profile/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        expected['id'] = id
        self.assertEqual(result, expected)

        # Attempt update to invalid value
        record['tz_id'] = 9999
        response = self.call_endpoint('/profile/%s' % id, 'put', data=record)
        self.assertEqual(response.status_code, 405, 'put unexpected message=%s'
                         % response.get_json().get('message'))
        self.assertEqual(response.get_json()['message'],
                         'duplicate or other conflict')
