"""test_metrics

Tests for metrics

created 23-feb-2021 by richb@instantlinux.net
"""
import os
import tempfile
from unittest import mock
import yaml

import test_base
from apicrud import database, Metrics, ServiceConfig

import models


class TestMetrics(test_base.TestBase):

    def setUp(self):
        self.authorize(username=self.admin_name, password=self.admin_pw)

    def test_integer_increment(self):
        response = self.call_endpoint('/metric?name=api_calls_total&filter='
                                      '{"label":"resource=settings"}', 'get')
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result['count'], 1)
        value = result['items'][0]['value']

        # Make another call and verify it gets counted
        response = self.call_endpoint('/settings/x-75023275', 'get')
        self.assertEqual(response.status_code, 200)

        response = self.call_endpoint(
            '/metric?filter={"name":"api_calls_total",'
            '"label":"resource=settings"}', 'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['items'][0]['value'], value + 1)

        # Double-increment also works
        Metrics().store('api_calls_total', labels=['resource=settings'],
                        value=2)
        response = self.call_endpoint(
            '/metric?filter={"name":"api_calls_total",'
            '"label":"resource=settings"}', 'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['items'][0]['value'], value + 3)

    def test_prometheus_collect(self):
        response = self.call_endpoint('/metrics', 'get')
        self.assertEqual(response.status_code, 200)
        result = response.data.decode()
        self.assertIn("# TYPE api_start_timestamp gauge\n", result)
        self.assertIn("api_request_seconds_total{", result)
        self.assertIn("# TYPE process_virtual_memory_bytes gauge\n"
                      "process_virtual_memory_bytes{instance=", result)

        response = self.call_endpoint('/metrics?limit=1', 'get')
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(response.data.decode().count('n'), 3)

    def test_find_several(self):
        response = self.call_endpoint('/metric?offset=2&limit=5', 'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json().get('count'), 5)

        response = self.call_endpoint('/metric?filter={"uid":""}', 'get')
        self.assertEqual(response.status_code, 200)
        # this is just to ensure at least one user metric
        db_session = database.get_session(db_url=self.config.DB_URL)
        Metrics(uid=self.test_uid, db_session=db_session).store(
            'video_daily_total')
        db_session.remove()
        self.assertGreaterEqual(response.get_json().get('count'), 1)

    def test_uid_restricted(self):
        self.authorize(new_session=True)
        response = self.call_endpoint(
            '/metric?filter={"uid":"u-nobody"}', 'get')
        self.assertEqual(response.status_code, 403)
        response = self.call_endpoint(
            '/metric?filter={"uid":"%s"}' % self.test_uid, 'get')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.get_json().get('count'), 0)

        # Also check the collect function - TODO implement auth
        response = self.call_endpoint(
            '/metrics?filter={"uid":"u-nobody"}', 'get')
        self.assertEqual(response.status_code, 200)
        response = self.call_endpoint(
            '/metric?filter={"uid":"%s"}' % self.test_uid, 'get')
        self.assertEqual(response.status_code, 200)

    def test_bad_filter(self):
        response = self.call_endpoint(
            '/metric?filter={"label":"truncated', 'get')
        self.assertEqual(response.status_code, 405)
        response = self.call_endpoint(
            '/metrics?filter={"label":"alsotruncated', 'get')
        self.assertEqual(response.status_code, 405)

    def test_check_store_invalid(self):
        with self.assertRaises(AssertionError):
            Metrics().check('bogus_metric')
        with self.assertRaises(AssertionError):
            Metrics().check('api_calls_total')
        with self.assertRaises(AssertionError):
            Metrics().store('bogus_metric')
        with self.assertRaises(AssertionError):
            Metrics().store('api_key_auth_total', value=u'stringsdisallowed')

    def test_grant_limit(self):
        grant = 'photo_res_max'
        limit = 3
        metric = {grant: {'style': 'grant'}}

        db_session = database.get_session(db_url=self.config.DB_URL)
        response = self.call_endpoint('/grant', 'post', data=dict(
            name=grant, value=str(limit), uid=self.test_uid))
        self.assertEqual(response.status_code, 201)

        configfile = tempfile.mkstemp(prefix='_cfg')[1]
        with open(configfile, 'w') as f:
            yaml.dump(dict(metrics=metric), f)
        ServiceConfig(file=configfile, reset=True, models=models)

        self.authorize(new_session=True)
        for count in range(limit):
            self.assertTrue(
                Metrics(uid=self.test_uid, db_session=db_session).store(grant))
        response = self.call_endpoint(
            '/metric?filter={"name":"%s","uid":"%s"}' % (grant, self.test_uid),
            'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json().get('items'), [
            dict(labels=['uid=%s' % self.test_uid], name=grant, value=0)])
        self.assertFalse(
            Metrics(uid=self.test_uid, db_session=db_session).store(grant))

        # Restore settings
        path = os.path.join(os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..')), 'example')
        ServiceConfig(reset=True, models=models,
                      babel_translation_directories=(
                          'i18n;%s' % os.path.join(path, 'i18n')),
                      db_seed_file=os.path.join(path, 'db_seed.yaml'),
                      db_migrations=os.path.join(path, 'alembic'),
                      rbac_file='/tmp/rbac.yaml')

    def test_check_limit_decrement(self):
        grant = 'sms_monthly_total'
        db_session = database.get_session(db_url=self.config.DB_URL)
        metrics = Metrics(uid=self.test_uid, db_session=db_session)
        current = metrics.check(grant)
        metrics.store(grant)
        next = metrics.check(grant)
        self.assertEqual(next, current - 1)
        db_session.remove()

    def test_warn_threshold_50(self):
        grant = 'photo_daily_total'
        limit = 4
        metric = {grant: {'style': 'grant', 'notify': 50}}

        db_session = database.get_session(db_url=self.config.DB_URL)
        response = self.call_endpoint('/grant', 'post', data=dict(
            name=grant, value=str(limit), uid=self.test_uid))
        self.assertEqual(response.status_code, 201)

        configfile = tempfile.mkstemp(prefix='_cfg')[1]
        with open(configfile, 'w') as f:
            yaml.dump(dict(metrics=metric), f)
        ServiceConfig(file=configfile, reset=True, models=models)

        self.authorize(new_session=True)
        mock_messaging = mock.Mock()
        for count in range(limit):
            self.assertTrue(
                Metrics(uid=self.test_uid, db_session=db_session,
                        func_send=mock_messaging).store(grant))
        mock_messaging.assert_called_once_with(
            to_uid=self.test_uid, template='usage_notify',
            period='day', percent=metric[grant]['notify'], resource=grant)
        response = self.call_endpoint(
            '/metric?filter={"name":"%s","uid":"%s"}' % (grant, self.test_uid),
            'get')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json().get('items'), [
            dict(labels=['uid=%s' % self.test_uid], name=grant, value=0)])

        # Restore settings
        path = os.path.join(os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..')), 'example')
        ServiceConfig(reset=True, models=models,
                      babel_translation_directories=(
                          'i18n;%s' % os.path.join(path, 'i18n')),
                      db_seed_file=os.path.join(path, 'db_seed.yaml'),
                      db_migrations=os.path.join(path, 'alembic'),
                      rbac_file='/tmp/rbac.yaml')
