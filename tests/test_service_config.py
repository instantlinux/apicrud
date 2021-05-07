"""test_service_config

Tests for service_config class

created 14-aug-2020 by docker@instantlinux.net
"""

import logging
import os
import tempfile
import yaml

import test_base
from apicrud import ServiceConfig
import models


class TestServiceConfig(test_base.TestBase):

    def test_file_overrides(self):
        updates = dict(
            appname='Test', db_geo_support=True, log_level='warning')

        self.authorize(username=self.admin_name, password=self.admin_pw)
        response = self.call_endpoint('/config', 'get')
        self.assertEqual(response.status_code, 200)
        app_config = response.get_json()
        # TODO hack
        app_config.pop('ldap_params')

        configfile = tempfile.mkstemp(prefix='_cfg')[1]
        env_save = os.environ.pop('APPNAME', None)
        with open(configfile, 'w') as f:
            yaml.dump(updates, f)
        path = os.path.abspath(os.path.join(os.path.dirname(
            __file__), '..', 'example'))
        ServiceConfig(file=configfile, reset=True,
                      babel_translation_directories='i18n;' + (
                          os.path.join(path, 'i18n')),
                      db_seed_file=os.path.join(path, '..', 'tests', 'data',
                                                'db_fixture.yaml'),
                      db_migrations=os.path.join(path, 'alembic'),
                      models=models, rbac_file=app_config['rbac_file'])
        app_config.update(updates)
        app_config['log_level'] = logging.WARNING

        response = self.call_endpoint('/config', 'get')
        # TODO remove hack
        result = response.get_json()
        result.pop('ldap_params')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(result, app_config)

        # restore settings
        os.environ['APPNAME'] = env_save
        ServiceConfig(reset=True,
                      babel_translation_directories='i18n;' + (
                          os.path.join(path, 'i18n')),
                      db_seed_file=os.path.join(path, '..', 'tests', 'data',
                                                'db_fixture.yaml'),
                      db_migrations=os.path.join(path, 'alembic'),
                      models=models, rbac_file=app_config['rbac_file'])
        os.remove(configfile)

    def test_get_config_unauthorized(self):
        response = self.call_endpoint('/config', 'get')
        self.assertEqual(response.status_code, 403)

    def test_env_var_booleans(self):
        self.authorize(username=self.admin_name, password=self.admin_pw)
        os.environ['DB_GEO_SUPPORT'] = 'TRUE'
        os.environ['DEBUG'] = '0'
        with self.config_overrides(appname='Example'):
            response = self.call_endpoint('/config', 'get')
            result = response.get_json()
            self.assertEqual(response.status_code, 200)
            self.assertTrue(result['db_geo_support'])
            self.assertFalse(result['debug'])

            os.environ['DEBUG'] = 'NOTVALID'
            with self.assertRaises(AttributeError):
                ServiceConfig(reset=True)
            del os.environ['DEBUG']
            del os.environ['DB_GEO_SUPPORT']

    def test_set_one_value(self):
        new_value = 'testservice'

        self.authorize(username=self.admin_name, password=self.admin_pw)
        response = self.call_endpoint('/config', 'get')
        self.assertEqual(response.status_code, 200)
        app_config = response.get_json()
        # TODO - remove temporary hack
        app_config.pop('ldap_params')

        with self.config_overrides(service_name=new_value):
            app_config['service_name'] = new_value

            response = self.call_endpoint('/config', 'get')
            result = response.get_json()
            result.pop('ldap_params')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(result, app_config)

    def test_badconfig_raises_exception(self):
        with self.assertRaises(AttributeError):
            with self.config_overrides(invalid_entry=True):
                pass

    def test_empty_overrides_raises_exception(self):
        with self.assertRaises(AttributeError):
            with self.config_overrides():
                pass

    def test_metric__config_exception(self):
        funky_metric = dict(api_calls_total=dict(
            scope='instance', invalidkey=''))

        with self.assertRaises(AttributeError):
            with self.config_overrides(metrics=funky_metric):
                pass
