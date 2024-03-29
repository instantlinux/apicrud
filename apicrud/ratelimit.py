"""ratelimit.py

created 31-dec-2020 by richb@instantlinux.net
"""

from base64 import b64encode
from flask import g, request
import hashlib
import logging
from redis.exceptions import ConnectionError
import time

from . import state
from .grants import Grants
from .service_config import ServiceConfig


class RateLimit(object):
    """Rate Limiting

    Args:
      enable (bool): enable limits [default: config.RATELIMIT_ENABLE]
      interval (int): seconds to count limit [config.RATELIMIT_INTERVAL]
    """
    def __init__(self, enable=False, interval=None):
        self.config = ServiceConfig().config
        self.enable = enable or self.config.RATELIMIT_ENABLE
        self.interval = interval or self.config.RATELIMIT_INTERVAL
        self.redis = state.redis_conn

    def call(self, limit=None, service='*', uid=None):
        """Apply the granted rate limit for uid to a given service
        Two redis keys are used, for even and odd intervals as measured
        modulo the Unix epoch time. The current interval's key is
        incremented if we haven't reached the limit yet, then we delete
        that key at first call seen next interval and increment the other
        key. The keys expire within interval-1 seconds to keep the cache clear
        after the user stops sending calls.

        Args:
          limit (int): limit for interval [default: from Grants]
          service (str): name of a service
          uid (str): a user ID

        Returns:
          bool: true if limit exceeded
        """
        if not self.enable:
            return False
        uid = uid or self._get_request_uid()
        if not uid:
            # No limit on anonymous requests, TODO make this smarter to
            #  protect against brute-force DDOS / security attacks
            return False
        limit = limit or Grants().get('ratelimit', uid=uid)
        curr = round(time.time()) % (self.interval * 2) // self.interval
        key = 'rate:%s:%s:%d' % (service, uid, curr)
        altkey = 'rate:%s:%s:%d' % (service, uid, 0 if curr else 1)
        try:
            calls = self.redis.get(key)
        except ConnectionError as ex:
            logging.error(dict(action='ratelimit.call', message=str(ex)))
            return False
        if limit and not calls or int(calls.decode()) < limit:
            try:
                pipe = self.redis.pipeline()
                pipe.incr(key).expire(
                    key, self.interval - 1).delete(altkey).execute()
            except Exception as ex:
                logging.error(dict(action='ratelimit.call', message=str(ex)))
        else:
            logging.info(dict(action='ratelimit.call', uid=uid,
                              service=service, message='limit exceeded'))
            return True
        return False

    def reset(self, service='*', uid=None):
        """Clear the current entry for a service

        Args:
          service (str): name of a service
          uid (str): a user ID
        """
        self.redis.delete('rate:%s:%s:0' % (service, uid))
        self.redis.delete('rate:%s:%s:1' % (service, uid))

    def _get_request_uid(self):
        """Examine headers to find uid
        """
        header_auth = self.config.HEADER_AUTH_APIKEY
        if header_auth in request.headers:
            try:
                prefix, secret = request.headers.get(header_auth).split('.')
            except ValueError:
                return None
            secret = b64encode(
                hashlib.sha1(secret.encode()).digest())[:8].decode('utf8')
            # TODO confirm whether this drops first use of apikey
            return g.session.get(None, secret, key_id=prefix, arg='sub')
        elif request.authorization:
            return request.authorization.username
