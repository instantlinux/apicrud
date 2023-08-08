"""test_messages

Tests for messages controller

created 22-oct-2019 by richb@instantlinux.net
"""

from unittest import mock

import test_base


class TestMessages(test_base.TestBase):

    def setUp(self):
        self.authorize()
        self.list = dict(
            name='My Message Board', description='For message testing',
            uid=self.test_uid)
        patcher = mock.patch('messaging.send_contact.delay')
        self.mock_send = patcher.start()
        response = self.call_endpoint('/list', 'post', data=self.list)
        if response.status_code != 405 or (
                'duplicate' not in response.get_json()['message']):
            self.assertEqual(response.status_code, 201)
        self.list_id = response.get_json().get('id')
        self.authorize(new_session=True)

    def test_add_and_fetch_message(self):
        record = dict(subject='Posting 1', content='Lorem Ipsum',
                      list_id=self.list_id)
        expected = dict(
            published=None, recipient_id=None,
            sender_id=self.test_uid, viewed=None, status='active',
            privacy='secret', uid=self.test_uid,
            owner=self.test_person_name, rbac='dru', **record)

        response = self.call_endpoint('/message', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/message/%s' % id, 'get')
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        del result['created']
        expected['id'] = id
        self.assertEqual(result, expected)

    def test_update_message(self):
        record = dict(subject='Posting 3', content='Lorem Ipsum dolor sit',
                      list_id=self.list_id)
        updated = dict(subject='Revised Posting')
        expected = dict(
            published=None, recipient_id=None,
            sender_id=self.test_uid, viewed=None, status='active',
            privacy='secret', rbac='dru', uid=self.test_uid,
            owner=self.test_person_name, **record)

        response = self.call_endpoint('/message', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/message/%s' % id, 'put', data=dict(
            record, **updated))
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))
        response = self.call_endpoint('/message/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        del result['modified']
        # del expected['list_id']
        expected.update(updated)
        expected['id'] = id
        self.assertEqual(result, expected)

    def test_message_delete(self):
        record = dict(subject='Random drivel', content='Moral outrage',
                      list_id=self.list_id)
        expected = dict(
            published=None, recipient_id=None,
            sender_id=self.test_uid, viewed=None, status='disabled',
            privacy='secret', uid=self.test_uid,
            rbac='dru', owner=self.test_person_name, **record)

        response = self.call_endpoint('/message', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/message/%s' % id, 'delete')
        self.assertEqual(response.status_code, 204)

        # The record should still exist, with disabled status
        response = self.call_endpoint('/message/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        expected['id'] = id
        self.assertEqual(result, expected)

        # Force delete -- should no longer exist
        response = self.call_endpoint('/message/%s?force=true' % id, 'delete')
        self.assertEqual(response.status_code, 204)
        response = self.call_endpoint('/message/%s' % id, 'get')
        result = response.get_json()
        self.assertEqual(response.status_code, 404)
