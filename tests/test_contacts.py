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
        self.adm_default_identity = 'user@example.com'

    def test_add_and_fetch_contact(self):
        record = dict(
            carrier=None, label='home', type='email', privacy='invitee',
            info='addme@conclave.events', uid=self.test_uid)
        expected = dict(
            status='unconfirmed', muted=False, rank=2, rbac='dru',
            owner=self.test_person_name, **record)
        response = self.call_endpoint('/contact', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        self.mock_messaging.assert_has_calls([
            mock.call(to=id, template='contact_add', token=mock.ANY,
                      type='email')])
        response = self.call_endpoint('/contact/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        expected['id'] = id
        self.assertEqual(result, expected)

    def test_update_contact(self):
        record = dict(
            label='work', type='email', info='testr@conclave.events',
            uid=self.test_uid, muted=False, privacy='member')
        updated = dict(
            label='mobile', info='changed@conclave.events')
        expected = dict(
            carrier=None, status='unconfirmed', rbac='dru',
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
        del result['created']
        del result['modified']
        del result['rank']
        expected.update(dict(id=id, **updated))
        self.assertEqual(result, expected)
        self.mock_messaging.assert_has_calls([
            mock.call(to=id, template='contact_add', token=mock.ANY,
                      type='email')])

    def test_confirm_contact(self):
        record = dict(
            carrier=None, label='home', type='email', privacy='invitee',
            info='confirmme@conclave.events', uid=self.test_uid)
        expected = dict(
            status='unconfirmed', muted=False, rbac='dru',
            owner=self.test_person_name, **record)
        confirmed = dict(
            auth='person', info=record['info'], iss=self.config.JWT_ISSUER,
            name=self.test_person_name, sub=self.test_uid, type=record['type'])

        response = self.call_endpoint('/contact', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        token = response.get_json()['token']
        self.mock_messaging.assert_has_calls([
            mock.call(to=id, template='contact_add', token=mock.ANY,
                      type='email')])
        response = self.call_endpoint('/contact/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        del result['rank']
        expected['id'] = id
        self.assertEqual(result, expected)

        confirmed['contact_id'] = id
        response = self.call_endpoint('/contact/confirm/%s' % token, 'post')
        result = response.get_json()
        del result['exp']
        del result['jti']
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
        del result['created']
        self.assertEqual(result, expected)

    @pytest.mark.slow
    def test_add_too_many_contacts(self):
        max_contacts = self.config.DEFAULT_GRANTS.get('contacts')
        contact = dict(
            carrier=None, label='home', type='email', privacy='invitee')

        with self.scratch_account('rsmith', 'Robin Smith') as acc:
            response = self.call_endpoint('/grant?filter={"name":"contacts"}',
                                          'get')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['items'], [dict(
                id='%s:contacts' % acc.uid, name='contacts', value='8',
                uid=acc.uid, rbac='r', status='active')])

            calls = []
            for i in range(max_contacts - 1):
                response = self.call_endpoint('/contact', 'post', data=dict(
                    info='email%d@conclave.events' % i,
                    uid=acc.uid, **contact))
                self.assertEqual(response.status_code, 201, 'post message=%s' %
                                 response.get_json().get('message'))
                calls.append(
                    mock.call(
                        to=response.get_json().get('id'),
                        template='contact_add', token=mock.ANY, type='email'))
            response = self.call_endpoint('/contact', 'post', data=dict(
                info='email%d@conclave.events' % max_contacts, uid=acc.uid,
                **contact))
            self.assertEqual(
                response.status_code, 405, 'unexpected message=%s' %
                response.get_json().get('message'))
            self.assertEqual(response.get_json(), dict(
                message=u'user limit exceeded', allowed=max_contacts))
            self.mock_messaging.assert_has_calls(calls)

    def test_get_contact_restricted(self):
        """Attempt to fetch private contact from an unprivileged user
        """
        expected = dict(message='access denied', id=self.adm_contact_2)
        response = self.call_endpoint(
            '/contact/%s' % self.adm_contact_2, 'get')
        self.assertEqual(response.status_code, 403, 'unexpected message=%s' %
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

    def test_update_contact_conflict_existing(self):
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

    def test_update_bad_email(self):
        record = dict(
            label='work', type='email', info='testr2@conclave.events',
            uid=self.test_uid, privacy='member')
        updated = dict(
            label='mobile', type='email', info='invalidemail',
            uid=self.test_uid)
        response = self.call_endpoint('/contact', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        self.mock_messaging.assert_has_calls([
            mock.call(to=id, template='contact_add', token=mock.ANY,
                      type='email')])
        response = self.call_endpoint('/contact/%s' % id, 'put', data=updated)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.get_json().get('message'),
                         'invalid email address')
