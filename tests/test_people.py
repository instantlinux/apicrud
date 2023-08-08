"""test_people

Tests for people controller

created 28-oct-2019 by richb@instantlinux.net
"""

import pytest
from unittest import mock

import test_base


class TestPeople(test_base.TestBase):

    def setUp(self):
        self.authorize()

    @pytest.mark.slow
    def test_add_and_fetch_person(self):
        record = dict(name='Teddy Johnson', identity='tj@conclave.events')
        expected = dict(
            lists=[], status='active', privacy='public',
            referrer_id=self.test_uid, rbac='dru', **record)
        contact = dict(count=1, items=[dict(
            info=record['identity'], label='home', privacy='member',
            type='email', muted=False, rank=1, modified=None, carrier=None,
            owner=record['name'], status='unconfirmed')])

        response = self.call_endpoint('/person', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/person/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        expected['id'] = id
        self.assertEqual(result, expected)
        response = self.call_endpoint('/contact?filter={"info":"%s"}' %
                                      record['identity'], 'get')
        result = response.get_json()
        contact['items'][0]['uid'] = id
        del result['items'][0]['id']
        del result['items'][0]['created']
        # TODO validate rbac after it's fixed
        del result['items'][0]['rbac']
        self.assertEqual(result, contact)

    def test_update_person(self):
        record = dict(name='Sarah Lee', identity='sarah@conclave.events')
        updated = dict(name='Sarah Lee', privacy='invitee')
        expected = dict(
            lists=[], status='active', privacy='public',
            referrer_id=self.test_uid, rbac='dru', **record)
        response = self.call_endpoint('/person', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/person/%s' % id, 'put', data=dict(
            record, **updated))
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))
        response = self.call_endpoint('/person/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        del result['modified']
        expected.update(updated)
        expected['id'] = id
        self.assertEqual(result, expected)

    def test_person_delete(self):
        record = dict(name='President Number45',
                      identity='occupant@whitehouse.gov')
        expected = dict(
            status='disabled', privacy='public', lists=[],
            referrer_id=self.test_uid, rbac='dru', **record)

        response = self.call_endpoint('/person', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']

        response = self.call_endpoint('/person/%s' % id, 'delete')
        self.assertEqual(response.status_code, 204)

        # The record should still exist, with disabled status
        response = self.call_endpoint('/person/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        expected.update(record)
        expected['id'] = id
        self.assertEqual(result, expected)

        # Force delete -- should no longer exist
        response = self.call_endpoint('/person/%s?force=true' % id, 'delete')
        self.assertEqual(response.status_code, 204)
        response = self.call_endpoint('/person/%s' % id, 'get')
        result = response.get_json()
        self.assertEqual(response.status_code, 404)

    def test_update_primary_contact(self):
        record = dict(name='Witness Protected',
                      identity='oldaccount@conclave.events')
        updated = dict(info='newaccount@conclave.events', type='email')
        expected = dict(
            carrier=None, rank=1, status='unconfirmed', rbac='ru',
            label='home', privacy='member', muted=False,
            owner=record['name'], **updated)

        # Create a new person and fetch the new contact record
        response = self.call_endpoint('/person', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        uid = response.get_json()['id']
        response = self.call_endpoint('/contact?filter={"uid":"%s"}' % uid,
                                      'get')
        self.assertEqual(response.status_code, 200, 'get failed message=%s' %
                         response.get_json().get('message'))
        cid = response.get_json()['items'][0]['id']

        # Update the contact record and confirm contents
        response = self.call_endpoint('/contact/%s' % cid, 'put',
                                      data=dict(uid=uid, **updated))
        self.assertEqual(response.status_code, 200, 'put failed message=%s' %
                         response.get_json().get('message'))
        response = self.call_endpoint('/contact/%s' % cid, 'get')
        self.assertEqual(response.status_code, 200, 'get failed message=%s' %
                         response.get_json().get('message'))
        result = response.get_json()
        del result['created']
        del result['modified']
        self.assertEqual(result, dict(id=cid, uid=uid, **expected))
        self.mock_messaging.assert_has_calls([
            mock.call(to=cid, template='contact_add', token=mock.ANY,
                      type='email')])

        # Now make sure the identity also got updated
        response = self.call_endpoint('/person/%s' % uid, 'get')
        self.assertEqual(response.status_code, 200, 'get failed message=%s' %
                         response.get_json().get('message'))
        result = response.get_json()
        self.assertEqual(result['identity'], updated['info'])

    def test_person_update_disallowed_upon_confirm(self):
        """One person refers another, by invoking POST to /person with
        a name and email address. Update/delete is allowed by either
        person until the referred person confirms or RSVPs to an event.
        """
        invited = dict(name='Phil Acolyte', identity='acolyte@conclave.events')
        updated = dict(name='El Diablo', privacy='invitee')

        response = self.call_endpoint('/person', 'post', data=invited)
        self.assertEqual(response.status_code, 201)
        uid = response.get_json()['id']
        response = self.call_endpoint('/contact?filter={"info":"%s"}' %
                                      invited['identity'], 'get')
        result = response.get_json()
        cid = result['items'][0]['id']

        response = self.call_endpoint('/contact/confirmation_get/%s' %
                                      cid, 'get')
        self.assertEqual(response.status_code, 200)
        self.mock_messaging.assert_has_calls([
            mock.call(to=cid, template='contact_add', token=mock.ANY,
                      type='email')])
        token = response.get_json()['token']
        response = self.call_endpoint('/contact/confirm/%s' % token, 'post')
        self.assertEqual(response.status_code, 200)

        response = self.call_endpoint('/person/%s' % uid, 'put', data=dict(
            invited, **updated))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json().get('message'), 'access denied')

    def test_add_invalid(self):
        record = dict(name='Rogue',
                      identity='r@conclave.events', id='x-notvalid')
        expected = dict(message='id is a read-only property',
                        title='Bad Request')

        response = self.call_endpoint('/person', 'post', data=record)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.get_json(), expected)

    def test_add_duplicate_person(self):
        record = dict(name='Mary Jones', identity='maryj@conclave.events')
        expected = dict(
            lists=[], status='active', privacy='public',
            referrer_id=self.test_uid, rbac='dru', **record)
        response = self.call_endpoint('/person', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/person/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        expected['id'] = id
        self.assertEqual(result, expected)
        response = self.call_endpoint('/person', 'post', data=record)
        self.assertEqual(response.status_code, 405)
        result = response.get_json()
        del result['data']
        self.assertEqual(result, dict(message='duplicate or other conflict'))

    # TODO - test that access disabled after contact-confirm
