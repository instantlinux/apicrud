"""apikey

created 26-dec-2020 by richb@instantlinux.net
monolith broken out 18-apr-2021
"""
from datetime import timedelta
from flask import abort, g, request
from flask_babel import _
import logging
from sqlalchemy.orm.exc import NoResultFound

from .. import AccessControl, SessionAuth, Metrics
from ..utils import utcnow

APIKEYS = {}


class APIKey(SessionAuth):
    def access(self, apikey, otp=None):
        """Access using API key

        Args:
          apikey (str): the API key
          otp (str): 6 or 8-digit one-time password
        Returns:
          dict: uid, scopes (None if not authorized)
        """
        global APIKEYS
        acc = AccessControl()
        key_id, secret = apikey.split('.')
        if key_id not in APIKEYS or utcnow() > APIKEYS[key_id]['expires']:
            # Note - local caching in APIKEYS global var reduces database
            # queries on Accounts table
            uid, scopes = acc.apikey_verify(key_id, secret)
            if not uid:
                return None
            try:
                account = g.db.query(self.models.Account).filter_by(
                    uid=uid, status='active').one()
            except NoResultFound:
                logging.info(dict(action='api_key', uid=uid,
                                  message='account not active'))
                return None
            except Exception as ex:
                logging.error(dict(action='api_key', message=str(ex)))
                return None
            APIKEYS[key_id] = dict(
                account_id=account.id,
                expires=utcnow() + timedelta(seconds=self.config.REDIS_TTL),
                identity=account.owner.identity,
                roles=['admin', 'user'] if account.is_admin else ['user'],
                scopes=[item.name for item in scopes],
                totp=account.totp, uid=uid)
            APIKEYS[key_id]['roles'] += self.get_roles(uid)
        item = APIKEYS[key_id]
        uid = item['uid']
        if self.config.LOGIN_MFA_APIKEY:
            if self.config.LOGIN_MFA_REQUIRED and not item['totp']:
                abort(403, _(u'please configure MFA'))
            if item['totp'] and not self.totp_bypass(uid) and (
                    request.url_rule.rule.split('/')[3] != 'auth'):
                abort(401, _(u'no valid TOTP cookie, please re-auth'))
        duration = (self.login_admin_limit if 'admin' in item['roles']
                    else self.login_session_limit)
        token = acc.apikey_hash(secret)[:8]
        ses = None
        try:
            # Look for existing session in redis cache
            ses = g.session.get(
                uid, token, arg='auth', key_id=key_id).split(':')
        except AttributeError:
            ses = g.session.create(uid, item['roles'], acc=item['account_id'],
                                   identity=item['identity'],
                                   ttl=duration, key_id=key_id, nonce=token)
        if ses:
            return dict(uid=uid, scopes=item['scopes'])


def auth(apikey, required_scopes=None):
    """ API key authentication for openapi securitySchemes

    Args:
      apikey (str): the key
      required_scopes (list): permissions requested

    Returns:
      dict: uid if successful (None otherwise)
    """
    if len(apikey) > 96 or '.' not in apikey:
        return None
    retval = APIKey().access(apikey)
    if not retval:
        return retval
    if required_scopes and (set(required_scopes) & set(retval['scopes']) !=
                            set(required_scopes)):
        logging.info(dict(action='api_key', prefix=apikey.split('.')[0],
                          scopes=retval['scopes'], message='denied'))
        return None
    Metrics().store('api_key_auth_total')
    return retval
