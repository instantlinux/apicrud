"""test_trashcan

Tests for trashcan controller

created 25-may-2021 by richb@instantlinux.net
"""
import pytest

import test_base


class TestTrashcan(test_base.TestBase):

    def test_delete_and_purge_single(self):
        location = dict(address='1600 Pennsylvania Ave', city='Washington',
                        state='DC', name='The White House')

        with self.scratch_account('jcollector', 'Jason Collector'):
            response = self.call_endpoint('/location', 'post', data=location)
            self.assertEqual(response.status_code, 201)
            id = response.get_json()['id']

            response = self.call_endpoint('/location/%s' % id, 'delete')
            self.assertEqual(response.status_code, 204)

            response = self.call_endpoint('/trashcan', 'get')
            self.assertEqual(response.status_code, 200)
            result = response.get_json()
            self.assertEqual(result['count'], 1)
            self.assertEqual(result['items'][0]['id'], '%s-%s' % (
                'location', id))

            response = self.call_endpoint('/trashcan/location-%s' % id, 'get')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['status'], 'disabled')

            response = self.call_endpoint('/trashcan/location-%s' % id,
                                          'delete')
            self.assertEqual(response.status_code, 204)
            response = self.call_endpoint('/trashcan', 'get')
            self.assertEqual(response.status_code, 200)
            result = response.get_json()
            self.assertEqual(result['count'], 0)

    @pytest.mark.slow
    def test_delete_restore(self):
        record = dict(address='633 West Fifth St', city='Los Angeles',
                      state='CA', name='US Bank Tower')

        self.authorize()
        response = self.call_endpoint('/location', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']

        response = self.call_endpoint('/location/%s' % id, 'delete')
        self.assertEqual(response.status_code, 204)

        response = self.call_endpoint('/trashcan', 'get')
        self.assertEqual(response.status_code, 200)
        count = response.get_json()['count']
        self.assertGreaterEqual(count, 1)

        response = self.call_endpoint('/trashcan/location-%s' % id, 'put',
                                      data=dict(status='active'))
        self.assertEqual(response.status_code, 200)

        response = self.call_endpoint('/trashcan', 'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['count'], count - 1)

        # cleanup
        response = self.call_endpoint('/location/%s?force=true' % id, 'delete')
        self.assertEqual(response.status_code, 204)

    @pytest.mark.slow
    def test_trash_all_resources(self):

        with self.scratch_account('hgather', 'Hunter Gatherer') as acc:
            record = dict(name='Test1', uid=acc.uid, scopes=[self.scope_id])
            response = self.call_endpoint('/apikey', 'post', data=record)
            self.assertEqual(response.status_code, 201)
            response = self.call_endpoint('/apikey/%s' %
                                          response.get_json()['id'], 'delete')
            self.assertEqual(response.status_code, 204)

            record = dict(name='Test1')
            response = self.call_endpoint('/category', 'post', data=record)
            self.assertEqual(response.status_code, 201)
            response = self.call_endpoint('/category/%s' %
                                          response.get_json()['id'], 'delete')
            self.assertEqual(response.status_code, 204)

            record = dict(info='14155551515', type='sms', carrier='att')
            response = self.call_endpoint('/contact', 'post', data=record)
            self.assertEqual(response.status_code, 201)
            response = self.call_endpoint('/contact/%s' %
                                          response.get_json()['id'], 'delete')
            self.assertEqual(response.status_code, 204)

            record = dict(name='Test1', key='testing', secret='s3kr3t',
                          settings_id=self.settings_id, vendor='acme')
            response = self.call_endpoint('/credential', 'post', data=record)
            self.assertEqual(response.status_code, 201)
            response = self.call_endpoint('/credential/%s' %
                                          response.get_json()['id'], 'delete')
            self.assertEqual(response.status_code, 204)

            record = dict(name='Test1')
            response = self.call_endpoint('/list', 'post', data=record)
            self.assertEqual(response.status_code, 201)
            response = self.call_endpoint('/list/%s' %
                                          response.get_json()['id'], 'delete')
            self.assertEqual(response.status_code, 204)

            record = dict(subject='Test1', content='testing')
            response = self.call_endpoint('/message', 'post', data=record)
            self.assertEqual(response.status_code, 201)
            response = self.call_endpoint('/message/%s' %
                                          response.get_json()['id'], 'delete')
            self.assertEqual(response.status_code, 204)

            record = dict(name='Jiminy Fidget', identity='jfidget@example.com')
            response = self.call_endpoint('/person', 'post', data=record)
            self.assertEqual(response.status_code, 201)
            response = self.call_endpoint('/person/%s' %
                                          response.get_json()['id'], 'delete')
            self.assertEqual(response.status_code, 204)

            record = dict(item='employer', value='Test1')
            response = self.call_endpoint('/profile', 'post', data=record)
            self.assertEqual(response.status_code, 201)
            response = self.call_endpoint('/profile/%s' %
                                          response.get_json()['id'], 'delete')
            self.assertEqual(response.status_code, 204)

            response = self.call_endpoint(
                '/trashcan?filter={"resource":"profile"}', 'get')
            self.assertEqual(response.status_code, 200)
            result = response.get_json()
            self.assertEqual(result['count'], 1)

            response = self.call_endpoint('/trashcan', 'get')
            self.assertEqual(response.status_code, 200)
            result = response.get_json()
            self.assertEqual(result['count'], 8)

            ids = ','.join([item['id'] for item in result['items']])
            response = self.call_endpoint('/trashcan/%s' % ids, 'delete')
            self.assertEqual(response.status_code, 204)

    @pytest.mark.slow
    def test_trashcan_bad_params(self):
        username = 'pstovall'
        with self.scratch_account(username, 'Perry Stovall') as acc:
            response = self.call_endpoint('/trashcan/contact-x-invalid', 'get')
            self.assertEqual(response.status_code, 404)

            self.authorize(username=self.admin_name, password=self.admin_pw)
            response = self.call_endpoint('/profile', 'post', data=dict(
                item='gender', value='nonbinary', privacy='invitee'))
            self.assertEqual(response.status_code, 201)
            id = response.get_json()['id']
            response = self.call_endpoint('/profile/%s' % id, 'delete')
            self.assertEqual(response.status_code, 204)

            # Try to examine or remove someone else's trash
            self.authorize(username, acc.password)
            response = self.call_endpoint('/trashcan/profile-%s' % id, 'get')
            self.assertEqual(response.status_code, 403)
            response = self.call_endpoint('/trashcan/profile-%s' % id,
                                          'delete')
            self.assertEqual(response.status_code, 403)

            # Pass bad params
            response = self.call_endpoint('/trashcan?filter={"invalid"', 'get')
            self.assertEqual(response.status_code, 405)
            self.assertIn(u'invalid filter specified',
                          response.get_json()['message'])

    def test_trashcan_filtering(self):
        username = 'hching'
        with self.scratch_account(username, 'Heather Ching'):
            # Empty filter or null ID is OK
            response = self.call_endpoint('/trashcan?filter={}', 'get')
            self.assertEqual(response.status_code, 200)
            response = self.call_endpoint(
                '/trashcan?filter={"id":null}', 'get')
            self.assertEqual(response.status_code, 200)

            record = dict(name='Test-2')
            response = self.call_endpoint('/list', 'post', data=record)
            self.assertEqual(response.status_code, 201)
            response = self.call_endpoint('/list/%s' %
                                          response.get_json()['id'], 'delete')
            self.assertEqual(response.status_code, 204)

            response = self.call_endpoint(
                '/trashcan?filter={"name":"*","resource":"list"}', 'get')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['count'], 1)

            response = self.call_endpoint(
                '/trashcan?filter={"bogus":"*"}', 'get')
            self.assertEqual(response.status_code, 405)
            self.assertEqual(response.get_json()['message'],
                             u'invalid filter key')

            response = self.call_endpoint(
                '/trashcan?filter={"uid":"%s"}' % self.admin_uid, 'get')
            self.assertEqual(response.status_code, 403)

            response = self.call_endpoint(
                '/trashcan?filter={"name":"T%","resource":"list"}', 'get')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['count'], 1)

            response = self.call_endpoint('/trashcan?sort=name:desc', 'get')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['count'], 1)
            response = self.call_endpoint('/trashcan?sort=id', 'get')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['count'], 1)

    @pytest.mark.slow
    def test_trashcan_cursor_pagination(self):
        with self.scratch_account('xstradford', 'Xavier Stradford') as acc:
            # Create / delete 9 resources of mixed types
            expected = self._create_pagination_fixture(acc.uid)

            # Read and verify in chunks of 3
            cursor_next, index = (None, 0)
            for page in range(3):
                uripath = '/trashcan?limit=3'
                if cursor_next:
                    uripath += '&cursor_next=%s' % cursor_next
                response = self.call_endpoint(uripath, 'get')
                result = response.get_json()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(result['count'], 3)
                for item in result['items']:
                    item.pop('created')
                    item.pop('id')
                    self.assertEqual(item, expected[index])
                    index += 1
                cursor_next = result.get('cursor_next')

            self.assertFalse('cursor_next' in result)

    @pytest.mark.slow
    def test_trashcan_offset_pagination(self):
        with self.scratch_account('jespinosa', 'Janice Espinosa') as acc:
            expected = self._create_pagination_fixture(acc.uid)

            response = self.call_endpoint(
                '/trashcan?limit=3&offset=0', 'get')
            self.assertEqual(response.status_code, 405)
            self.assertEqual(
                response.get_json()['message'],
                u'use cursor pagination or specify resource in filter')

            # Read the first 5 items, starting with chunk of 3
            index = 0
            for offset in (0, 3):
                response = self.call_endpoint(
                    '/trashcan?limit=3&offset=%d&filter={"resource":"%s"}'
                    % (offset, 'list'), 'get')
                result = response.get_json()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(result['count'], 3 if offset == 0 else 2)
                for item in result['items']:
                    item.pop('created')
                    item.pop('id')
                    self.assertEqual(item, expected[index])
                    index += 1

            # Confirm we have 3 deleted messages
            response = self.call_endpoint(
                '/trashcan?limit=4&offset=%d&filter={"resource":"%s"}'
                % (0, 'message'), 'get')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['count'], 3)

    def _create_pagination_fixture(self, uid):
        """Generates 9 records, for pagination tests

        Args:
          uid (str): the user ID
        Returns: (list) 9 dicts containing expected results
        """
        expected = ([
            dict(name='testing-%d' % i, modified=None, rbac='dru',
                 resource='list', status='disabled', uid=uid)
            for i in range(5)
        ] + [
            dict(name='testing %d' % i, modified=None, rbac='dru',
                 resource='message', status='disabled', uid=uid)
            for i in range(3)
        ] + [
            dict(name='employer', modified=None, rbac='dru',
                 resource='profile', status='disabled', uid=uid)
        ])

        # Create / delete 9 resources of the above three types
        for i in range(5):
            response = self.call_endpoint('/list', 'post', data=dict(
                name='testing-%d' % i))
            self.assertEqual(response.status_code, 201)
            response = self.call_endpoint(
                '/list/%s' % response.get_json()['id'], 'delete')
            self.assertEqual(response.status_code, 204)
        for i in range(3):
            response = self.call_endpoint('/message', 'post', data=dict(
                subject='testing %d' % i, content='testing'))
            self.assertEqual(response.status_code, 201)
            response = self.call_endpoint(
                '/message/%s' % response.get_json()['id'], 'delete')
            self.assertEqual(response.status_code, 204)
        response = self.call_endpoint('/profile', 'post', data=dict(
            item='employer', value='Test1'))
        self.assertEqual(response.status_code, 201)
        response = self.call_endpoint('/profile/%s' %
                                      response.get_json()['id'], 'delete')
        self.assertEqual(response.status_code, 204)
        return expected
