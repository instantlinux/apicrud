"""test_lists

Tests for lists controller

created 22-oct-2019 by richb@instantlinux.net
"""

import test_base


class TestLists(test_base.TestBase):

    def setUp(self):
        self.authorize()

    def test_add_and_fetch_list(self):
        record = dict(name='list1', category_id=self.cat_id)
        expected = dict(
            category='default', description=None, members=[],
            status='active', privacy='public', uid=self.test_uid,
            owner=self.test_person_name, rbac='dghijru', **record)
        response = self.call_endpoint('/list', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/list/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        expected['id'] = id
        self.assertEqual(result, expected)

    def test_update_list(self):
        record = dict(
            name='list2', category_id=self.cat_id)
        updated = dict(privacy='member')
        expected = dict(
            category='default', description=None, members=[],
            status='active', uid=self.test_uid,
            owner=self.test_person_name, rbac='dghijru', **record)

        response = self.call_endpoint('/list', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/list/%s' % id, 'put', data=dict(
            record, **updated))
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))
        response = self.call_endpoint('/list/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        del result['modified']
        expected.update(updated)
        expected['id'] = id
        self.assertEqual(result, expected)

    def test_list_delete(self):
        record = dict(
            name='list3', category_id=self.cat_id)
        expected = dict(
            category='default', description=None, members=[],
            status='disabled', privacy='public', uid=self.test_uid,
            owner=self.test_person_name, rbac='dghijru', **record)

        response = self.call_endpoint('/list', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/list/%s' % id, 'delete')
        self.assertEqual(response.status_code, 204)

        # The record should still exist, with disabled status
        response = self.call_endpoint('/list/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        expected['id'] = id
        self.assertEqual(result, expected)

        # Force delete -- should no longer exist
        response = self.call_endpoint('/list/%s?force=true' % id, 'delete')
        self.assertEqual(response.status_code, 204)
        response = self.call_endpoint('/list/%s' % id, 'get')
        result = response.get_json()
        self.assertEqual(response.status_code, 404)

    def test_list_add_members(self):
        record = dict(
            name='list4', category_id=self.cat_id)
        members = (self.test_uid, self.global_admin_id)
        expected = dict(
            category='default', description=None, uid=self.test_uid,
            status='active', privacy='public', owner=self.test_person_name,
            rbac='dghijru', **record)

        response = self.call_endpoint('/list', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/list/%s' % id, 'put', data=dict(
            record, **dict(members=members)))
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))
        response = self.call_endpoint('/list/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        del result['modified']
        expected.update(dict(members=set(members), id=id))
        result['members'] = set(result['members'])
        self.assertEqual(result, expected)
