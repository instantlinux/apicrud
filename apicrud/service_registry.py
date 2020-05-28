"""service_registry.py

Services or the UI discover one another through this service registry.
Each microservice instance submits its identity and capabilities to
this central registry, implemented as expiring redis keys which are
updated at a fixed frequency. Encryption provides modest protection
against injection attacks.

created 8-may-2020 by richb@instantlinux.net

"""

import json
import logging
import redis
import socket
import threading

from .aes_encrypt import AESEncrypt
from . import utils

refresh_thread = None
service_data = {}
params = {}


class ServiceRegistry(object):

    def __init__(self, config, ttl=None, redis_conn=None):
        global params, refresh_thread
        self.config = config
        if not redis_conn and hasattr(config, 'redis_conn'):
            redis_conn = config.redis_conn
        if not params:
            params = dict(
                aes=AESEncrypt(self.config.REDIS_AES_SECRET),
                connection=(
                    redis_conn or redis.Redis(host=config.REDIS_HOST,
                                              port=config.REDIS_PORT, db=0)),
                interval=config.REGISTRY_INTERVAL,
                ttl=ttl or config.REGISTRY_TTL)
        if not refresh_thread:
            refresh_thread = threading.Thread()

    def register(self, resource_endpoints, service_name=None,
                 instance_id=socket.gethostname(), tcp_port=None):
        global service_data
        try:
            ipv4 = socket.gethostbyname(instance_id)
        except socket.gaierror:
            ipv4 = None
        service_data['info'] = dict(
            endpoints=resource_endpoints, ipv4=ipv4,
            port=tcp_port or self.config.PORT,
            public_url=self.config.PUBLIC_URL,
            created=utils.utcnow().replace(microsecond=0).isoformat())
        service_data['name'] = service_name or self.config.SERVICE_NAME
        service_data['id'] = instance_id
        logging.info(dict(action='service.register', id=instance_id,
                          name=service_data['name'], **service_data['info']))
        refresh_thread = threading.Timer(1, ServiceRegistry.update, ())
        refresh_thread.start()

    @staticmethod
    def update():
        key = 'reg:%s:%s' % (service_data['name'], service_data['id'])
        try:
            params['connection'].set(key, params['aes'].encrypt(json.dumps(
                service_data['info'])), ex=params['ttl'], nx=False)
        except Exception as ex:
            logging.error('action=registry.update message=%s' % str(ex))
        refresh_thread = threading.Timer(params['interval'],
                                         ServiceRegistry.update, ())
        refresh_thread.start()

    def find(self, service_name=None):
        """ Finds one or all services

        returns:
          dict - instances (list of registered services)
                 url_map (public url for each top-level resource)
        """

        key = 'reg:%s:*' % service_name if service_name else 'reg:*'
        retval = []
        url_map = {}
        for instance in params['connection'].scan_iter(match=key):
            try:
                info = json.loads(params['aes'].decrypt(
                    params['connection'].get(instance)))
                info['name'], info['id'] = instance.decode().split(':')[1:]
                retval.append(info)
            except TypeError:
                # A decrypt failure probably means another cluster
                # is sharing the same redis instance (e.g. in a dev env)
                # so skip over those service instances
                continue
            except Exception as ex:
                logging.warn('action=registry.find key=%s exception=%s' %
                             (instance, str(ex)))
            if not info.get('endpoints'):
                continue
            for resource in info['endpoints']:
                if resource not in url_map:
                    url_map[resource] = info[
                        'public_url'] + self.config.BASE_URL
                elif url_map[resource] != info[
                        'public_url'] + self.config.BASE_URL:
                    logging.warning(dict(
                        action='registry.find',
                        message='instance serves different public URL',
                        resource=resource, instance1=instance.decode(),
                        url1=info['public_url'], url2=url_map[resource]))
        return dict(instances=retval, url_map=url_map)
