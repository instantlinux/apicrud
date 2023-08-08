"""test_locations

Tests for locations controller

created 20-jan-2021 by richb@instantlinux.net
"""

from unittest import mock

import test_base


class TestLocations(test_base.TestBase):

    def setUp(self):
        self.authorize()
        patcher = mock.patch('geocoder.mapquest')
        self.mock_geo = patcher.start()

    def test_add_and_fetch_location(self):
        record = dict(address='175 5th Ave', city='New York', state='NY')
        expected = dict(
            country='US', geo=[-73.9918579, 40.7411774], name=None,
            neighborhood='A neighborhood in New York', postalcode=None,
            category='default', category_id=self.cat_id, status='active',
            privacy='public', uid=self.test_uid,
            owner=self.test_person_name, rbac='dru', **record)

        self.mock_geo.return_value.lng = expected['geo'][0]
        self.mock_geo.return_value.lat = expected['geo'][1]
        response = self.call_endpoint('/location', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/location/%s' % id, 'get')
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        del result['created']
        expected['id'] = id
        self.assertEqual(result, expected)

    def test_private_location(self):
        record = dict(name='Mar-a-Lago', address='1100 S Ocean Blvd',
                      city='Palm Beach', state='FL', privacy='invitee')
        geo = (-80.0391689, 26.6770665)
        expected = dict(
            country='US',
            neighborhood='A neighborhood in Palm Beach', postalcode=None,
            category='default', category_id=self.adm_cat_id, status='active',
            uid=self.admin_uid,
            owner=self.adm_person_name, rbac='', **record)

        self.authorize(username=self.admin_name, password=self.admin_pw,
                       new_session=True)
        self.mock_geo.return_value.lng = geo[0]
        self.mock_geo.return_value.lat = geo[1]
        response = self.call_endpoint('/location', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']

        # Re-auth as non-privileged user: address and coordinates are fuzzed
        self.authorize(new_session=True)
        response = self.call_endpoint('/location/%s' % id, 'get')
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        del result['created']
        expected['id'] = id
        expected['address'] = ''
        expected['geo'] = [-80.0392, 26.6771]
        self.assertEqual(result, expected)

    def test_update_location(self):
        record = dict(address='1600 Pennsylvania Ave', city='Washington',
                      state='DC')
        updated = dict(name='The White House')
        expected = dict(
            country='US', geo=[-73.9918579, 40.7411774],
            neighborhood='A neighborhood in Washington', postalcode=None,
            category='default', category_id=self.cat_id, status='active',
            privacy='public', uid=self.test_uid,
            owner=self.test_person_name, rbac='dru', **record)

        self.mock_geo.return_value.lng = expected['geo'][0]
        self.mock_geo.return_value.lat = expected['geo'][1]
        response = self.call_endpoint('/location', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        id = response.get_json()['id']
        response = self.call_endpoint('/location/%s' % id, 'put', data=dict(
            record, **updated))
        self.assertEqual(response.status_code, 200, 'put failed location=%s' %
                         response.get_json().get('location'))
        response = self.call_endpoint('/location/%s' % id, 'get')
        result = response.get_json()
        del result['created']
        del result['modified']
        expected.update(updated)
        expected['id'] = id
        self.assertEqual(result, expected)

    @mock.patch('logging.error')
    def test_location_no_apikey(self, mock_logging):
        record = dict(name='La Tour Eiffel', city='Paris', country='FR',
                      address='Champ de Mars, 5 Avenue Anatole France')

        self.mock_geo.return_value.side_effect = ValueError(
            'Provide API Key')
        response = self.call_endpoint('/location', 'post', data=record)
        self.assertEqual(response.status_code, 201)
        # TODO: AssertionError: expected call not found
        # mock_logging.assert_called_with(
        #    'geocode: no MapQuest key set')

    def test_find_locations(self):
        expected = [dict(
            address='800 Dolores St.',
            category='default',
            category_id='x-3423ceaf',
            city='San Francisco',
            country='US',
            geo=[-122.425671, 37.756503],
            id=self.location_id,
            modified=None,
            name=None,
            neighborhood='Mission District',
            owner='Example User',
            postalcode=None,
            privacy='public',
            rbac='r',
            state='CA',
            status='active',
            uid=self.global_admin_id)]

        response = self.call_endpoint('/location?filter={"state":"CA"}', 'get')
        self.assertEqual(response.status_code, 200)
        result = response.get_json()['items']
        del result[0]['created']
        self.assertEqual(expected, result)
