"""test_main

Tests for top-level main app

created 17-oct-2019 by richb@instantlinux.net
"""

import test_base

import apicrud._version as apiver
from example import _version


class TestMain(test_base.TestBase):

    # tutorial:
    # https://www.patricksoftwareblog.com/unit-testing-a-flask-application/

    def test_healthcheck(self):
        expected = dict(
            description=self.config.APPNAME + ' - ' + 'main',
            notes=['build_date:' + _version.build_date,
                   'schema:b972839aee75',
                   'apicrud_version:' + apiver.__version__],
            releaseId='unset',
            serviceId='main',
            status='pass',
            version=_version.__version__)
        response = self.call_endpoint('/health', 'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), expected)

    def test_auth(self):
        expected = self.settings_id
        response = self.call_endpoint('/auth', 'post', data=dict(
            username=self.username, password=self.password))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['settings_id'], expected)
        response = self.call_endpoint('/auth', 'post', data=dict(
            username=self.username, password=''))
        self.assertEqual(response.status_code, 400)

    def test_logout(self):
        self.authorize()
        response = self.call_endpoint('/settings/x-75023275', 'get')
        self.assertEqual(response.status_code, 200)
        response = self.call_endpoint('/logout', 'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), dict(message='logged out'))
        response = self.call_endpoint('/settings/x-75023275', 'get')
        self.assertEqual(response.status_code, 401)

    def test_get_settings_noauth(self):
        response = self.call_endpoint('/settings/x-75023275', 'get')
        self.assertEqual(response.status_code, 401)

    def test_get_settings_auth(self):
        expected = dict(
            id='x-75023275',  # theme_id='x-05a720bf',
            administrator_id=self.global_admin_id, country='US',
            default_storage_id=None,
            default_cat_id='x-3423ceaf', default_hostlist_id=None,
            lang='en_US', name='global', privacy='public',
            smtp_port=587, smtp_smarthost='smtp.gmail.com',
            smtp_credential_id=None, tz_id=598, url='http://localhost:3000',
            window_title='Example apicrud Application', rbac='r')
        self.authorize()
        response = self.call_endpoint('/settings/x-75023275', 'get')
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        result.pop('created', None)
        result.pop('modified', None)
        self.assertEqual(result, expected)

    def test_get_location_auth(self):
        expected = dict(
            address='800 Dolores St.',
            category='default',
            category_id='x-3423ceaf',
            city='San Francisco',
            country='US',
            geo=[-122.425671, 37.756503],
            id='x-67673434',
            name=None,
            neighborhood='Mission District',
            owner='Example User',
            postalcode=None,
            privacy='public',
            rbac='r',
            state='CA',
            status='active',
            uid=self.global_admin_id)
        self.authorize()
        response = self.call_endpoint('/location/x-67673434', 'get')
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        del result['created']
        self.assertEqual(result, expected)

    # TODO not yet implemented - extraneous-key rejection
    """
    def test_strict_validation(self):
        record = dict(id=self.adm_cat_id, uid=self.admin_uid,
                      name='default', extraneous='rejected')
        self.authorize(username=self.admin_name, password=self.admin_pw)
        response = self.call_endpoint('/category/%s' % self.adm_cat_id, 'put',
                                      data=record)
        self.assertEqual(response.status_code, 400, 'unexpected')
    """
