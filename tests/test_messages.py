"""test_messages

Tests for messages controller

created 22-oct-2019 by richb@instantlinux.net
"""

import mock

# from apicrud import database
import test_base


class TestMessages(test_base.TestBase):

    def setUp(self):
        self.authorize()
        self.list = dict(
            name='My Message Board', description='For message testing',
            uid=self.test_uid)
        patcher = mock.patch('example.messaging.send.delay')
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
        del(result['created'])
        del(expected['list_id'])
        expected['id'] = id
        self.assertEqual(result, expected)

    """
    TODO these rely on Guest
    @mock.patch('example.messaging.send.delay')
    def test_fetch_message_invitee(self, mock_messaging):
        record = dict(subject='Posting 2', content='Greetings of the season',
                      list_id=self.list_id, privacy='invitee')
        person = dict(name='Gareth Tang', identity='gareth@conclave.lists')

        expected = dict(
            published=None, recipient_id=None,
            sender_id=self.test_uid, viewed=None, uid=self.test_uid,
            owner=self.test_person_name, status='active',
            rbac='r', **record)

        response = self.call_endpoint('/message', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        message_id = response.get_json()['id']

        response = self.call_endpoint('/person', 'post', data=person)
        self.assertEqual(response.status_code, 201)
        uid = response.get_json().get('id')
        response = self.call_endpoint('/guest', 'post', data=dict(
            uid=uid, list_id=self.list_id))
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['ids'][0]

        # Log in as the new guest
        db = database.get_session()
        magic = db.query(Guest).filter_by(id=id).one().magic
        db.remove()
        self.guest_authorize(id, magic)

        response = self.call_endpoint('/message/%s' % message_id, 'get')
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        del(result['created'])
        del(expected['list_id'])
        expected['id'] = message_id
        self.assertEqual(result, expected)

    @mock.patch('example.messaging.send.delay')
    def test_mailblast_guests(self, mock_send):
        record = dict(subject='Posting 2', content='Lorem Ipsum dolor',
                      list_id=self.list_id, mailblast=True,
                      mailto=['not_responded'])
        person = dict(name='Sally Liu', identity='liu118@conclave.lists')

        response = self.call_endpoint('/person', 'post', data=person)
        self.assertEqual(response.status_code, 201)
        response = self.call_endpoint('/guest', 'post', data=dict(
            list_id=self.list_id, uid=response.get_json().get('id')))
        self.assertEqual(response.status_code, 201)
        gid = response.get_json()['ids'][0]

        response = self.call_endpoint('/message', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        result = response.get_json()
        self.assertEqual(result['count'], 2)
        self.assertEqual(gid in result['ids'], True)

        # should have 2 email actions - guest-invite and host-message
        mock_send.assert_has_calls([
            mock.call(self.test_uid, [gid], 'invite', guest_id=gid,
                      hosts=self.test_person_name, list_id=self.list_id,
                      list=self.list['name'], starts=mock.ANY),
            mock.call(self.test_uid, [mock.ANY, gid], 'host_message',
                      hosts=self.test_person_name, list_id=self.list_id,
                      list=self.list['name'], starts=mock.ANY,
                      message=record['content'], subject=record['subject']
                      )])

        # a blank list should return 405
        record['mailto'] = ['waitlist']
        response = self.call_endpoint('/message', 'post', data=record)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.get_json(), dict(message='no recipients'))
    """

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
        del(result['created'])
        del(result['modified'])
        del(expected['list_id'])
        expected.update(updated)
        expected['id'] = id
        self.assertEqual(result, expected)

    def test_message_delete(self):
        record = dict(subject='Random drivel', content='Moral outrage',
                      list_id=self.list_id)
        expected = dict(
            published=None, recipient_id=None,
            sender_id=self.test_uid, viewed=None, status='disabled',
            privacy='secret', rbac='dru', uid=self.test_uid,
            owner=self.test_person_name, **record)

        response = self.call_endpoint('/message', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/message/%s' % id, 'delete')
        self.assertEqual(response.status_code, 204)

        # The record should still exist, with disabled status
        response = self.call_endpoint('/message/%s' % id, 'get')
        result = response.get_json()
        del(result['created'])
        del(expected['list_id'])
        expected['id'] = id
        self.assertEqual(result, expected)

        # Force delete -- should no longer exist
        response = self.call_endpoint('/message/%s?force=true' % id, 'delete')
        # TODO sometimes this happens
        # WARNING {'message': "(pymysql.err.IntegrityError) (1451, 'Cannot
        # delete or update a parent row: a foreign key constraint fails
        # (`conclave_2`.`listmessages`, CONSTRAINT `listmessages_ibfk_1`
        # FOREIGN KEY (`message_id`) REFERENCES `messages` (`id`) ON DELETE
        # CASCADE)')\n[SQL: DELETE FROM messages WHERE messages.id =
        # %(id_1)s]\n[parameters: {'id_1': 'x-0YQvLkrM'}

        self.assertEqual(response.status_code, 204)
        response = self.call_endpoint('/message/%s' % id, 'get')
        result = response.get_json()
        self.assertEqual(response.status_code, 404)
