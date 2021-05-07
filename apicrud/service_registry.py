"""service_registry.py

created 8-may-2020 by richb@instantlinux.net
"""

import json
import logging
import socket
import threading

from .aes_encrypt import AESEncrypt
from .service_config import ServiceConfig
from . import state, utils

refresh_thread = None
service_data = {}
params = {}


class ServiceRegistry(object):
    """Service Registry

    Services or the UI discover one another through this service
    registry.  Each microservice instance submits its identity and
    capabilities to this central registry, implemented as expiring redis
    keys which are updated at a fixed frequency. Encryption provides
    modest protection against injection attacks.

    Args:
      aes_secret (str): an AES secret [default: config.REDIS_AES_SECRET]
      public_url (str): URL to serve [default: config.PUBLIC_URL]
      reload_params (bool): force param reload, for unit-testing
      ttl (int): how long to cache instance's registration
    """

    def __init__(self, aes_secret=None, public_url=None,
                 reload_params=False, ttl=None):
        global params, refresh_thread
        self.config = config = ServiceConfig().config
        self.public_url = public_url or config.PUBLIC_URL
        self.redis_conn = state.redis_conn
        if not params or reload_params:
            params = dict(
                aes=AESEncrypt(aes_secret or config.REDIS_AES_SECRET),
                interval=config.REGISTRY_INTERVAL,
                ttl=ttl or config.REGISTRY_TTL)
        if not refresh_thread:
            refresh_thread = threading.Thread()

    def register(self, resource_endpoints, service_name=None,
                 instance_id=socket.gethostname(), tcp_port=None):
        """register an instance serving a list of endpoints

        Args:
          resource_endpoints (list of str): controller endpoints served
          service_name (str): microservice name
          instance_id (str): unique ID of instance
          tcp_port (int): port number of service
        """

        global service_data

        start = utils.utcnow().timestamp()
        try:
            ipv4 = socket.gethostbyname(instance_id)
        except socket.gaierror:
            ipv4 = None
        try:
            redis_ip = socket.gethostbyname(self.config.REDIS_HOST)
        except socket.gaierror:
            redis_ip = None
        service_data['info'] = dict(
            endpoints=resource_endpoints, ipv4=ipv4,
            port=tcp_port or self.config.APP_PORT, public_url=self.public_url,
            created=utils.utcnow().replace(microsecond=0).isoformat())
        service_data['name'] = service_name or self.config.SERVICE_NAME
        service_data['id'] = instance_id
        logging.info(dict(action='service.register', id=instance_id,
                          redis_ip=redis_ip,
                          name=service_data['name'], duration='%.3f' %
                          (utils.utcnow().timestamp() - start),
                          **service_data['info']))
        self._save_entry()
        refresh_thread = threading.Timer(1, ServiceRegistry.update, ())
        refresh_thread.start()

    def get(self):
        """return service registration for local instance

        Returns: dict(name, id, info)
          Key info is dict(endpoints, ipv4, port, public_url, created)
        """
        return service_data

    @staticmethod
    def update():
        """background function to update registration at the defined
        interval from local memory cache, until the instance
        terminates.
        """

        ServiceRegistry._save_entry()
        refresh_thread = threading.Timer(params['interval'],
                                         ServiceRegistry.update, ())
        refresh_thread.start()

    @staticmethod
    def _save_entry():
        key = 'reg:%s:%s' % (service_data['name'], service_data['id'])
        try:
            state.redis_conn.set(key, params['aes'].encrypt(json.dumps(
                service_data['info'])), ex=params['ttl'], nx=False)
        except Exception as ex:
            logging.error('action=registry.update message=%s' % str(ex))

    def find(self, service_name=None):
        """ Finds one or all services

        Args:
          service_name (str): a service, or None for all

        Returns:
          dict - instances (list of registered services)
                 url_map (public url for each top-level resource)
        """

        key = 'reg:%s:*' % service_name if service_name else 'reg:*'
        retval = []
        url_map = {}
        for instance in self.redis_conn.scan_iter(match=key):
            try:
                info = json.loads(params['aes'].decrypt(
                    self.redis_conn.get(instance)))
                info['name'], info['id'] = instance.decode().split(':')[1:]
                retval.append(info)
            except (TypeError, json.JSONDecodeError, UnicodeDecodeError):
                # A decrypt failure probably means another cluster
                # is sharing the same redis instance (e.g. in a dev env)
                # so skip over those service instances
                continue
            except Exception as ex:
                logging.error('action=registry.find key=%s exception=%s' %
                              (instance, str(ex)))
                continue
            if not info.get('endpoints'):
                continue
            base_url = ServiceConfig().config.BASE_URL
            for resource in info['endpoints']:
                if resource not in url_map:
                    url_map[resource] = info['public_url'] + base_url
                elif resource != 'metric' and url_map[resource] != info[
                        'public_url'] + base_url:
                    logging.warning(dict(
                        action='registry.find', resource=resource,
                        message='misconfigured cluster serves two URLs',
                        instance1=':'.join(instance.decode().split(':')[1:]),
                        url1=info['public_url'] + base_url,
                        url2=url_map[resource]))
        return dict(instances=retval, url_map=url_map)
