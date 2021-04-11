"""session_auth

created 26-mar-2020 by richb@instantlinux.net
"""
from datetime import datetime, timedelta
from flask import g, redirect, request
from flask_babel import _
import jwt
import logging
import os
import redis
from sqlalchemy.orm.exc import NoResultFound

from .access import AccessControl
from .account_settings import AccountSettings
from .const import Constants
from .database import db_abort
from .initialize import oauth
from .metrics import Metrics
from .service_config import ServiceConfig
from .service_registry import ServiceRegistry
from .utils import gen_id, utcnow

APIKEYS = {}
OC = {}
REDIS = None


class SessionAuth(object):
    """Session Authorization

    Functions for login, password and role authorization

    Args:
      func_send(function): name of function for sending message
      roles_from (obj): model for which to look up authorizations
    """

    def __init__(self, func_send=None, roles_from=None, redis_conn=None):
        global REDIS

        config = self.config = ServiceConfig().config
        self.models = ServiceConfig().models
        self.jwt_secret = config.JWT_SECRET
        self.login_session_limit = config.LOGIN_SESSION_LIMIT
        self.login_admin_limit = config.LOGIN_ADMIN_LIMIT
        self.func_send = func_send
        self.oauth = oauth['init']
        self.roles_from = roles_from
        self.redis_conn = (
            redis_conn or REDIS or redis.Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT, db=0))
        REDIS = self.redis_conn

    def account_login(self, username, password, method='local', otp=None):
        """Log in using local or OAuth2 credentials

        Args:
          username (str): account name or email
          password (str): credential
          method (str): local, or google / facebook / twitter etc
          otp (str): one-time or backup password

        Returns:
          dict:
            Fields include jwt_token (contains uid / account ID),
            ID of entry in settings database, and a sub-dictionary
            with mapping of endpoints registered to microservices
        """
        from .auth import local_func, oauth2_func, totp_func

        logmsg = dict(action='login', username=username, method=method)
        acc = AccessControl()
        if acc.auth and 'pendingtotp' in acc.auth:
            # TODO make this pendingtotp finite-state logic more robust
            if otp:
                ret = totp_func.login(username, otp,
                                      redis_conn=self.redis_conn)
                if ret[1] != 200:
                    return ret
                return self._login_accepted(username, ret[2], method)
            else:
                logging.info(dict(error='otp token omitted', **logmsg))
                return dict(message=_(u'access denied')), 403
        elif not method or method == 'local':
            ret = local_func.login(username, password)
            if ret[1] != 200:
                return ret
            return self._login_accepted(username, ret[2], 'local')
        elif method in self.config.AUTH_PARAMS.keys():
            return oauth2_func.login(username, password, method,
                                     cache=Ocache())
        else:
            msg = _(u'unsupported login method')
            logging.error(dict(message=msg, **logmsg))
            return dict(message=msg), 500

    def _login_accepted(self, username, account, method):
        """Login accepted from provider: create a session

        Args:
          username (str): the account's unique username
          account (obj): account object in database
          method (str): method, e.g. local or google
        """
        account.last_login = datetime.utcnow()
        account.invalid_attempts = 0
        g.db.commit()
        # connexion doesn't support cookie auth. probably just as well,
        #  this forced me to implement a better JWT design with nonce token
        # https://github.com/zalando/connexion/issues/791
        #  TODO come up with a standard approach, this is still janky
        #  and does not do signature validation (let alone PKI)

        # TODO research concerns raised in:
        # https://paragonie.com/blog/2017/03/jwt-json-web-tokens-is-bad-
        #  standard-that-everyone-should-avoid
        acc = AccessControl()
        action = 'login'
        duration = (self.login_admin_limit if account.is_admin
                    else self.login_session_limit)
        if (account.password_must_change and method == 'local'):
            roles = ['person', 'pwchange']
            duration = 300
        elif not account.totp_secret and self.config.LOGIN_MFA_REQUIRED and (
                method == 'local' or self.config.LOGIN_MFA_EXTERNAL):
            roles = ['mfarequired']
            duration = 300
        elif account.totp_secret and (
                method == 'local' or self.config.LOGIN_MFA_EXTERNAL) and not (
                    acc.auth and 'pendingtotp' in acc.auth):
            roles = ['pendingtotp']
            action = 'totp_challenge'
            duration = 120
        # TODO parameterize model name contact
        elif (g.db.query(self.models.Contact).filter(
                self.models.Contact.info == account.owner.identity,
                self.models.Contact.type == 'email'
                ).one().status == 'active'):
            roles = ['admin', 'user'] if account.is_admin else ['user']
            if self.roles_from:
                roles += self.get_roles(account.uid, self.roles_from)
        else:
            roles = []
        logging.info('action=%s username=%s method=%s account_id=%s' %
                     (action, username, method, account.id))
        ses = g.session.create(account.uid, roles, acc=account.id,
                               identity=account.owner.identity, ttl=duration)
        if ses:
            retval = dict(
                jwt_token=jwt.encode(
                    ses, self.jwt_secret, algorithm='HS256').decode('utf-8'),
                resources=ServiceRegistry().find()['url_map'],
                settings_id=account.settings_id)
            if hasattr(account.settings, 'default_storage_id'):
                retval['storage_id'] = account.settings.default_storage_id
            if 'pendingtotp' not in roles:
                Metrics().store('logins_success_total')
            if method == 'local':
                return retval, 201
            else:
                return redirect('%s%s?token=%s' % (
                    account.settings.url,
                    self.config.AUTH_LANDING_PAGE, retval['jwt_token']))
        else:
            return db_abort(_(u'login session trouble'), action='login')

    def account_add(self, username, uid):
        """Add an account with the given username

        Args:
          username (str): new / unique username
          uid (str): existing user
        """
        logmsg = dict(action='account_add', username=username)
        try:
            settings_id = g.db.query(
                self.models.Settings).filter_by(name='global').one().id
        except Exception as ex:
            return db_abort(str(ex), message=u'failed to read global settings',
                            **logmsg)
        account = self.models.Account(
            id=gen_id(), uid=uid, name=username,
            password_must_change=True, password='',
            settings_id=settings_id, status='active')
        try:
            g.db.add(account)
            g.db.commit()
        except Exception as ex:
            return db_abort(str(ex), rollback=True, **logmsg)
        return dict(id=account.id, uid=uid), 201

    def api_access(self, apikey, totp_cookie=None):
        """Access using API key

        Args:
          apikey (str): the API key
          totp_cookie (str): a TOTP bypass cookie
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
                scopes=[item.name for item in scopes], uid=uid)
            if self.roles_from:
                APIKEYS[key_id]['roles'] += self.get_roles(uid,
                                                           self.roles_from)
        item = APIKEYS[key_id]
        uid = item['uid']
        logging.debug(dict(action='api_key', uid=uid, scopes=item['scopes']))
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

    def auth_params(self):
        """Get authorization info"""
        account_id = AccessControl().account_id
        settings = AccountSettings(account_id, db_session=g.db)
        try:
            account = g.db.query(self.models.Account).filter_by(
                id=account_id).one()
        except Exception as ex:
            return db_abort(str(ex), action='auth_params')
        retval = dict(
            resources=ServiceRegistry().find()['url_map'],
            settings_id=settings.get.id, totp=account.totp)
        storage_id = settings.get.default_storage_id
        if storage_id:
            retval['storage_id'] = storage_id
        return retval, 200

    def methods(self):
        """Return list of available auth methods"""
        internal_policy = self.config.LOGIN_INTERNAL_POLICY
        if not self.config.LOGIN_LOCAL:
            internal_policy = 'closed'
        ret = ['local'] if self.config.LOGIN_LOCAL else []
        for method in self.config.AUTH_PARAMS.keys():
            if os.environ.get('%s_CLIENT_ID' % method.upper()):
                ret.append(method)
        return dict(
            items=ret, count=len(ret),
            policies=dict(
                login_internal=internal_policy,
                login_external=self.config.LOGIN_EXTERNAL_POLICY)), 200

    def get_roles(self, uid, member_model, resource=None, id=None):
        """Get roles that match uid / id for a resource
        Each is in the form <resource>-<id>-<privacy level>

        Args:
          uid (str): User ID
          member_model (obj): the DB model that defines membership in resource
          resource (str): the resource that defines privacy (e.g. list)
          id (str): ID of the resource (omit if all are desired)
        Returns:
          list of str: authorized roles
        """
        acc = AccessControl()
        if not resource:
            resource = acc.primary_res
        column = '%s_id' % resource
        try:
            query = g.db.query(member_model).filter_by(uid=uid,
                                                       status='active')
            if id:
                query = query.filter_by(**{column: id})
        except Exception as ex:
            logging.warning('action=get_roles message="%s"' % str(ex))
        roles = []
        for record in query.all():
            if not hasattr(record, resource):
                continue
            # Skip first defined level (always 'public')
            for level in acc.privacy_levels[1:]:
                roles.append('%s-%s-%s' % (resource, getattr(record, column),
                                           level))
                if level == record.authorization:
                    break
        return roles

    def update_auth(self, member_model, id, resource=None, force=False):
        """Check current access, update if recently changed

        Args:
          member_model (obj): model (e.g. Guest) which defines membership in
            resource
          id (str): resource id of parent resource
          resource (str):
            parent resource for which membership should be checked
          force (bool): perform update regardless of logged-in permissions
        """
        acc = AccessControl()
        if not resource:
            resource = acc.primary_res
        current = set(acc.auth)
        if force or ('%s-%s-%s' % (resource, id, Constants.AUTH_INVITEE)
                     not in current):
            # TODO handle privilege downgrade member/host->invitee
            current |= set(self.get_roles(acc.uid, member_model,
                                          resource=resource, id=id))
            creds = request.authorization
            g.session.update(creds.username, creds.password, 'auth',
                             ':'.join(current))


# TODO this goes away when OAuth2 debugging is done
class Ocache(object):
    def __init__(self):
        if 'cache' not in OC:
            OC['cache'] = {}
        self.cache = OC['cache']

    def set(self, key, value, expires=None):
        self.cache[key] = value

    def get(self, key):
        return self.cache.get(key)


# Support openapi securitySchemes: basic_auth and api_key endpoints
def basic(username, password, required_scopes=None):
    """This is a modified basic-auth validation function. The auth login
    controller method generates a random 8-byte token, stores it in
    the session_manager object as token_auth, and sends it to javascript
    authProvider. The dataProvider must send it back to us as
    basic-auth (base64-encoded).

    Vulnerable to session-hijacking if auth packets aren't encrypted
    end to end, but "good enough" until OAuth2 effort is completed.

    Implemented because of https://github.com/zalando/connexion/issues/791

    Args:
      username (str): Session UID
      password (str): Session token
      required_scopes (list): not used
    Returns:
      dict: uid with the username passed in
    """

    session = g.session.get(username, password)
    token_auth = 'ok'
    if session is None or 'jti' not in session:
        token_auth = 'missing'
    elif session['jti'] != password or session['sub'] != username:
        token_auth = 'invalid'
    elif 'exp' in session and datetime.utcnow().strftime(
            '%s') > session['exp']:
        token_auth = 'expired'

    if token_auth != 'ok':
        logging.info('action=logout username=%s token_auth=%s' % (
            username, token_auth))
        if session:
            try:
                g.session.delete(username, password)
            except redis.exceptions.ConnectionError as ex:
                logging.error(dict(action='logout', message=str(ex)))
        return None
    return dict(uid=username)


def api_key(apikey, required_scopes=None):
    """ API key authentication

    Args:
      apikey (str): the key
      required_scopes (list): permissions requested

    Returns:
      dict: uid if successful (None otherwise)
    """
    models = ServiceConfig().models
    if len(apikey) > 96 or '.' not in apikey:
        return None
    # TODO - parameterize roles_from properly
    retval = SessionAuth(roles_from=models.List).api_access(apikey)
    if not retval:
        return retval
    if required_scopes and (set(required_scopes) & set(retval['scopes']) !=
                            set(required_scopes)):
        logging.info(dict(action='api_key', prefix=apikey.split('.')[0],
                          scopes=retval['scopes'], message='denied'))
        return None
    Metrics().store('api_key_auth_total')
    return retval
