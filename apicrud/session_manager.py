"""session_manager.py

Session Manager
  Each login session is stored as an encrypted JSON dict in redis, indexed
  by sub:token

created 8-may-2019 by richb@instantlinux.net
"""

from datetime import datetime, timedelta
import json
import logging
import random
import redis
import string
import time

from .aes_encrypt import AESEncrypt
from .service_config import ServiceConfig

saved_redis = None


class SessionManager(object):
    """Session Manager - for active user sessions

    Args:
      ttl (int): seconds until a session expires
      redis_conn (obj): connection to redis service
    """
    def __init__(self, ttl=None, redis_conn=None):
        global saved_redis

        self.config = ServiceConfig().config
        self.connection = (
            redis_conn or saved_redis or redis.Redis(
                host=self.config.REDIS_HOST,
                port=self.config.REDIS_PORT, db=0))
        saved_redis = self.connection
        self.ttl = ttl or self.config.REDIS_TTL
        self.aes = AESEncrypt(self.config.REDIS_AES_SECRET)

    def create(self, uid, roles, **kwargs):
        """Create a session, which is an encrypted JSON object with the values
        defined in https://tools.ietf.org/html/rfc7519 for JWT claim names:

        - exp - expiration time, as integer Unix epoch time
        - iss - a constant JWT_ISSUER
        - jti - JWT ID, the randomly-generated token
        - sub - the uid of a user

        We add these:

        - auth - authorized roles
        - any other key=value pairs the caller passes as kwargs

        The session automatically expires based on object's ttl. Part of
        the jti token is used in redis key, to allow a user to log into
        multiple sessions. The rest of the token is encrypted, to
        secure it from replay attack in the event redis traffic
        is compromised.

        Args:
          uid: User ID
          roles: Authorized roles
          nonce: a unique identifier for the token (random if not specified)
          ttl: duration of session (defaulted from class init)
        Returns:
          dict:
            Keys include auth (authorized roles), exp / iss / jti / sub
            (as above), along with parameters passed into this function
        """

        token = kwargs.pop('nonce', _gen_id(prefix=''))
        ttl = kwargs.pop('ttl', self.ttl)
        params = dict(
            auth=':'.join(roles),
            exp=(datetime.utcnow() + timedelta(
                seconds=ttl)).strftime('%s'),
            iss=self.config.JWT_ISSUER, jti=token, sub=uid
        )
        key = 'uid:%s:%s' % (uid, token[-3:])
        content = {**params, **kwargs}  # noqa
        if self.connection.set(key, self.aes.encrypt(json.dumps(
                content)), ex=ttl, nx=True):
            return content

    def get(self, uid, token, arg=None):
        """Get one or all key-value pairs stored by session create

        Args:
          uid (str): User ID
          token (str): The token value passed from create as 'jti'
          arg (str): key of desired value (None to fetch all)
        Returns:
          dict or str: single value or dictionary of all session keys
        """
        key = 'uid:%s:%s' % (uid, token[-3:])
        try:
            data = json.loads(self.aes.decrypt(
                self.connection.get(key)))
        except TypeError:
            return None
        except Exception as ex:
            logging.info('action=session.get uid=%s exception=%s' %
                         (uid, str(ex)))
            return None
        if data['jti'] != token:
            logging.warning('action=session.get message=rejected')
            return None
        if arg:
            return data[arg] if arg in data else None
        return data

    def update(self, uid, token, arg, value):
        """Update a specified session key

        Args:
          uid: User ID
          token (str): The token value passed from create as 'jti'
          arg (str): key to update
          value (str): new value for key
        """
        key = 'uid:%s:%s' % (uid, token[-3:])
        data = self.get(uid, token)
        data[arg] = value
        self.connection.set(key, self.aes.encrypt(
            json.dumps(data)), ex=self.ttl)

    def delete(self, uid, token):
        """Cancel a session

        Args:
          uid: User ID
          token (str): The token value passed from create as 'jti'
        """
        self.connection.delete('uid:%s:%s' % (uid, token[-3:]))


class Mutex:
    """Simple mutex implementation for non-clustered Redis

    Tried to implement this as inner class to DRY out the init,
    but ... no joy.

    Args:
      lockname (str): a unique name for the lock
      redis_host (str): IP or DNS name of redis service
      maxwait (int): seconds to wait for a lock
      ttl (int): seconds to hold lock
      redis_conn (obj): existing redis connection
    """
    def __init__(self, lockname, redis_host=None, maxwait=20,
                 ttl=0, redis_conn=None):
        config = ServiceConfig().config
        self.connection = (
            redis_conn or redis.Redis(host=redis_host,
                                      port=config.REDIS_PORT, db=0))
        self.ttl = ttl or config.REDIS_TTL
        self.lock_signature = _gen_id()
        self.lockname = lockname
        self.maxwait = maxwait

    def acquire(self):
        """Acquire a mutex lock

        Raises:
          TimeoutError: if the resource is unavailable
        """
        for retry in range(self.maxwait):
            if self.connection.set('mutex:%s' % self.lockname,
                                   self.lock_signature, ex=self.ttl, nx=True):
                return True
            time.sleep(1)
        raise TimeoutError('Unable to acquire mutex=%s' % self.lockname)

    def release(self):
        """Release a lock
        """
        if ((self.connection.get('mutex:%s' % self.lockname).decode('utf-8') !=
             self.lock_signature) or
                not self.connection.delete('mutex:%s' % self.lockname)):
            raise TimeoutError('Mutex held too long, may need a longer ttl')

    def __enter__(self):
        self.acquire()

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.release()


# TODO: resolve another DRY problem - this yields a circular dependency
# when invoked as 'import lib.utils'
def _gen_id(length=8, prefix='x-', chars=(
        '-' + string.digits + string.ascii_uppercase + '_' +
        string.ascii_lowercase)):
    def _int2base(x, chars, base=64):
        return _int2base(x // base, chars, base).lstrip(chars[0]) + chars[
            x % base] if x else chars[0]
    return (prefix +
            _int2base((datetime.utcnow() - datetime(2018, 1, 1)).days * 8 +
                      random.randint(0, 8), chars) +
            ''.join(random.choice(chars) for i in range(length - 3)))
