"""test_contacts

Tests for contacts controller

created 17-oct-2019 by richb@instantlinux.net
"""

import pytest
from unittest import mock

import test_base


class TestContacts(test_base.TestBase):

    def setUp(self):
        self.authorize()
        self.adm_default_identity = 'example@instantlinux.net'

    @mock.patch('messaging.send_contact.delay')
    def test_add_and_fetch_contact(self, mock_messaging):
        record = dict(
            carrier=None, label='home', type='email', privacy='invitee',
            info='addme@conclave.events', uid=self.test_uid)
        expected = dict(
            status='unconfirmed', muted=False, rank=1, rbac='dru',
            owner=self.test_person_name, **record)
        response = self.call_endpoint('/contact', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        mock_messaging.assert_has_calls([
            mock.call(to=id, template='contact_add', token=mock.ANY,
                      type='email')])
        response = self.call_endpoint('/contact/%s' % id, 'get')
        result = response.get_json()
        del(result['created'])
        expected['id'] = id
        self.assertEqual(result, expected)

    @mock.patch('messaging.send_contact.delay')
    def test_update_contact(self, mock_messaging):
        record = dict(
            label='work', type='email', info='testr@conclave.events',
            uid=self.test_uid, muted=False, privacy='member')
        updated = dict(
            label='mobile', info='changed@conclave.events')
        expected = dict(
            carrier=None, status='unconfirmed', rank=1, rbac='dru',
            owner=self.test_person_name, **record)

        response = self.call_endpoint('/contact', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/contact/%s' % id, 'put', data=dict(
            record, **updated))
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))
        response = self.call_endpoint('/contact/%s' % id, 'get')
        result = response.get_json()
        del(result['created'])
        del(result['modified'])
        expected.update(dict(id=id, **updated))
        self.assertEqual(result, expected)
        mock_messaging.assert_has_calls([
            mock.call(to=id, template='contact_add', token=mock.ANY,
                      type='email')])

    @mock.patch('messaging.send_contact.delay')
    def test_confirm_contact(self, mock_messaging):
        record = dict(
            carrier=None, label='home', type='email', privacy='invitee',
            info='confirmme@conclave.events', uid=self.test_uid)
        expected = dict(
            status='unconfirmed', muted=False, rank=1, rbac='dru',
            owner=self.test_person_name, **record)
        confirmed = dict(
            auth='pending', info=record['info'], iss=self.config.JWT_ISSUER,
            name=self.test_person_name, sub=self.test_uid, type=record['type'])

        response = self.call_endpoint('/contact', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        token = response.get_json()['token']
        mock_messaging.assert_has_calls([
            mock.call(to=id, template='contact_add', token=mock.ANY,
                      type='email')])
        response = self.call_endpoint('/contact/%s' % id, 'get')
        result = response.get_json()
        del(result['created'])
        expected['id'] = id
        self.assertEqual(result, expected)

        confirmed['contact_id'] = id
        response = self.call_endpoint('/contact/confirm/%s' % token, 'post')
        result = response.get_json()
        del(result['exp'])
        del(result['jti'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(result, confirmed)

    def test_get_admin_contact(self):
        expected = dict(
            carrier=None, id='x-4566a239', info=self.adm_default_identity,
            label='home', owner='Example User', uid=self.global_admin_id,
            privacy='public',
            muted=True, rank=1, rbac='r', status='active', type='email')
        response = self.call_endpoint('/contact/x-4566a239', 'get')
        self.assertEqual(response.status_code, 200, 'get failed message=%s' %
                         response.get_json().get('message'))
        result = response.get_json()
        del(result['created'])
        self.assertEqual(result, expected)

    @pytest.mark.slow
    @mock.patch('messaging.send_contact.delay')
    def test_add_too_many_contacts(self, mock_messaging):
        max_contacts = self.config.DEFAULT_GRANTS.get('contacts')
        account = dict(
            name='Robin Smith', username='rsmith',
            identity='rsmith@conclave.events')
        password = dict(new_password='dC5$#xHg', verify_password='dC5$#xHg')
        contact = dict(
            carrier=None, label='home', type='email', privacy='invitee')

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

        response = self.call_endpoint('/grant?filter={"name":"contacts"}',
                                      'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['items'], [dict(
            id='%s:contacts' % uid, name='contacts', value='8', uid=uid,
            rbac='r', status='active')])

        # TODO clarify why this reset_mock mock?
        mock_messaging.reset_mock()
        calls = []
        for i in range(max_contacts - 1):
            response = self.call_endpoint('/contact', 'post', data=dict(
                info='email%d@conclave.events' % i, uid=uid, **contact))
            self.assertEqual(response.status_code, 201, 'post message=%s' %
                             response.get_json().get('message'))
            # TODO why is this call happening?
            calls.append(mock.call.__bool__())
            calls.append(
                mock.call(
                    to=response.get_json().get('id'),
                    template='contact_add', token=mock.ANY, type='email'))
        response = self.call_endpoint('/contact', 'post', data=dict(
            info='email%d@conclave.events' % max_contacts, uid=uid,
            **contact))
        self.assertEqual(response.status_code, 405, 'unexpected message=%s' %
                         response.get_json().get('message'))
        self.assertEqual(response.get_json(), dict(
            message=u'user limit exceeded', allowed=max_contacts))
        mock_messaging.assert_has_calls(calls)

    def test_get_contact_restricted(self):
        """Attempt to fetch private contact from an unprivileged user
        """
        expected = dict(message='access denied', id=self.adm_contact_2)
        response = self.call_endpoint(
            '/contact/%s' % self.adm_contact_2, 'get')
        self.assertEqual(response.status_code, 403, 'get failed message=%s' %
                         response.get_json().get('message'))
        result = response.get_json()
        self.assertEqual(result, expected)

    def test_update_contact_disallowed(self):
        record = dict(uid=self.global_admin_id,
                      info='changeme@conclave.events',
                      label='home', type='email', status='unconfirmed')
        response = self.call_endpoint('/contact/x-4566a239', 'post',
                                      data=record)
        self.assertEqual(response.status_code, 405, 'unexpected message=%s' %
                         response.get_json().get('message'))
        response = self.call_endpoint('/contact/x-4566a239', 'put',
                                      data=record)
        self.assertEqual(response.status_code, 403, 'unexpected message=%s' %
                         response.get_json().get('message'))

    @mock.patch('messaging.send_contact.delay')
    def test_update_contact_conflict_existing(self, mock_messaging):
        record = dict(
            label='work', type='email', info='conflict@conclave.events',
            uid=self.test_uid, muted=False, privacy='member')
        updated = dict(info=self.adm_default_identity, type='email',
                       uid=self.test_uid)
        response = self.call_endpoint('/contact', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/contact/%s' % id, 'put', data=dict(
            record, **updated))
        self.assertEqual(response.status_code, 405, 'put failed message=%s' %
                         response.get_json().get('message'))
        self.assertEqual(response.get_json(),
                         dict(message='conflict with existing'))

    def test_create_not_allowed_other_user(self):
        person = dict(name='Rose Yang', identity='yang@conclave.events')
        record = dict(
            carrier=None, label='home', type='email', privacy='invitee')

        response = self.call_endpoint('/person', 'post', data=person)
        self.assertEqual(response.status_code, 201)
        uid = response.get_json()['id']
        response = self.call_endpoint('/contact', 'post', data=dict(
                info='rose@aol.com', uid=uid, **record))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json(), dict(message='access denied'))

    def test_contact_bad_email(self):
        record = dict(
            label='work', type='email', info='invalid',
            uid=self.test_uid, privacy='member')
        response = self.call_endpoint('/contact', 'post', data=record)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.get_json().get('message'),
                         'invalid email address')

    @mock.patch('messaging.send_contact.delay')
    def test_update_bad_email(self, mock_messaging):
        record = dict(
            label='work', type='email', info='testr2@conclave.events',
            uid=self.test_uid, privacy='member')
        updated = dict(
            label='mobile', type='email', info='invalidemail',
            uid=self.test_uid)
        response = self.call_endpoint('/contact', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        mock_messaging.assert_has_calls([
            mock.call(to=id, template='contact_add', token=mock.ANY,
                      type='email')])
        response = self.call_endpoint('/contact/%s' % id, 'put', data=updated)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.get_json().get('message'),
                         'invalid email address')
