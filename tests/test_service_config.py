"""test_service_config

Tests for service_config controller

created 14-aug-2020 by docker@instantlinux.net
"""

import logging
import os
import tempfile
import yaml

import test_base
from apicrud import ServiceConfig


class TestServiceConfig(test_base.TestBase):

    def test_file_overrides(self):
        updates = dict(
            appname='Test', db_geo_support=True, log_level='warning')

        self.authorize(username=self.admin_name, password=self.admin_pw)
        response = self.call_endpoint('/config', 'get')
        self.assertEqual(response.status_code, 200)
        app_config = response.get_json()

        configfile = tempfile.mkstemp(prefix='_cfg')[1]
        os.environ.pop('APPNAME', None)
        with open(configfile, 'w') as f:
            yaml.dump(updates, f)
        path = os.path.join(os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..')), 'example')
        ServiceConfig(file=configfile, reset=True,
                      babel_translation_directories='i18n;' + (
                          os.path.join(path, 'i18n')),
                      db_seed_file=os.path.join(path, 'db_seed.yaml'),
                      db_migrations=os.path.join(path, 'alembic'),
                      rbac_file=app_config['rbac_file'])
        app_config.update(updates)
        app_config['log_level'] = logging.WARNING

        response = self.call_endpoint('/config', 'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), app_config)
        os.remove(configfile)

    def test_get_config_unauthorized(self):
        response = self.call_endpoint('/config', 'get')
        self.assertEqual(response.status_code, 403)

    def test_env_var_booleans(self):

        self.authorize(username=self.admin_name, password=self.admin_pw)
        response = self.call_endpoint('/config', 'get')
        self.assertEqual(response.status_code, 200)
        app_config = response.get_json()

        os.environ['DB_GEO_SUPPORT'] = 'TRUE'
        os.environ['DEBUG'] = '0'
        path = os.path.join(os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..')), 'example')
        ServiceConfig(reset=True,
                      db_seed_file=app_config['db_seed_file'],
                      db_migrations=app_config['db_migrations'],
                      babel_translation_directories=(
                          'i18n;%s' % os.path.join(path, 'i18n')),
                      rbac_file=app_config['rbac_file'])
        app_config['db_geo_support'] = True

        response = self.call_endpoint('/config', 'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), app_config)

        os.environ['DEBUG'] = 'NOTVALID'
        with self.assertRaises(AttributeError):
            ServiceConfig(reset=True)

        del os.environ['DEBUG']
        del os.environ['DB_GEO_SUPPORT']
        # Restore settings
        ServiceConfig(reset=True,
                      db_seed_file=os.path.join(path, 'db_seed.yaml'),
                      db_migrations=os.path.join(path, 'alembic'),
                      babel_translation_directories=(
                          'i18n;%s' % os.path.join(path, 'i18n')),
                      rbac_file=app_config['rbac_file'])

    def test_set_one_value(self):
        new_value = 'testservice'

        self.authorize(username=self.admin_name, password=self.admin_pw)
        response = self.call_endpoint('/config', 'get')
        self.assertEqual(response.status_code, 200)
        app_config = response.get_json()

        ServiceConfig().set('service_name', new_value)
        app_config['service_name'] = new_value

        response = self.call_endpoint('/config', 'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), app_config)
