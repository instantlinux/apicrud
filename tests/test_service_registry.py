"""test_service_registry

Tests for service_registry class

created 21-jan-2021 by docker@instantlinux.net
"""

from unittest import mock

import test_base
from apicrud import ServiceRegistry


class TestServiceRegistry(test_base.TestBase):

    @mock.patch('logging.warning')
    @mock.patch('logging.info')
    def test_register_find(self, mock_logging, mock_warning):
        endpoints = ['account', 'location', 'message']
        expected_a = dict(
            instances=[dict(created=mock.ANY, endpoints=endpoints,
                            id='1.1.1.1', ipv4='1.1.1.1', name='test',
                            port=mock.ANY, public_url=mock.ANY)],
            url_map=dict(account=self.config.PUBLIC_URL + self.config.BASE_URL,
                         location=mock.ANY, message=mock.ANY))
        alt_url = 'http://test.com'
        expected_b = dict(
            instances=[dict(created=mock.ANY, endpoints=endpoints,
                            id='2.1.1.2', ipv4='2.1.1.2', name='test',
                            port=mock.ANY, public_url=alt_url)],
            url_map=dict(account=mock.ANY,
                         location=mock.ANY, message=mock.ANY))

        ServiceRegistry().register(
            endpoints, service_name='test', instance_id='1.1.1.1')
        mock_logging.assert_called_with(dict(
            action='service.register', created=mock.ANY, duration=mock.ANY,
            endpoints=endpoints, id='1.1.1.1', ipv4='1.1.1.1', name='test',
            port=self.config.APP_PORT, public_url=self.config.PUBLIC_URL,
            redis_ip=None))

        result = ServiceRegistry().find(service_name='test')
        self.assertEqual(result, expected_a)

        # Register another instance with different aes encryption to ensure
        #  it's ignored (use-case: dev / staging sharing a redis server)

        ServiceRegistry(
            reload_params=True,
            aes_secret='f523779a90f849e587f1d12e5189173e').register(
                endpoints, service_name='test', instance_id='9.1.1.9')
        result = ServiceRegistry().find(service_name='test')
        expected_a['instances'][0]['id'] = '9.1.1.9'
        expected_a['instances'][0]['ipv4'] = '9.1.1.9'
        self.assertEqual(result, expected_a)

        # Register another instance with different public_url to ensure
        #  a misconfigured cluster warning is triggered
        ServiceRegistry(public_url=alt_url).register(
            endpoints, service_name='test', instance_id='2.1.1.2')
        result = ServiceRegistry().find(service_name='test')
        self.assertCountEqual(result['instances'], expected_a['instances'] +
                              expected_b['instances'])
        mock_warning.assert_called_with(dict(
            action='registry.find', resource='message',
            message='misconfigured cluster serves two URLs',
            instance1='test:9.1.1.9',
            url1=self.config.PUBLIC_URL + self.config.BASE_URL,
            url2=alt_url + self.config.BASE_URL))
