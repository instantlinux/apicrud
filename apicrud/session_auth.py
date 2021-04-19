"""session_auth

created 26-mar-2020 by richb@instantlinux.net
"""
from flask import g, redirect, request
from flask_babel import _
import jwt
import logging
import os
import redis

from .access import AccessControl
from .account_settings import AccountSettings
from .const import Constants
from .database import db_abort
from .initialize import oauth
from .metrics import Metrics
from .service_config import ServiceConfig
from .service_registry import ServiceRegistry
from .utils import gen_id, utcnow

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
        if acc.auth and ('pendingtotp' in acc.auth or (otp and acc.apikey_id)):
            # TODO make this pendingtotp finite-state logic more robust
            if otp:
                ret = totp_func.login(username, otp,
                                      redis_conn=self.redis_conn)
                if ret[1] != 200:
                    return ret
                return self._login_accepted(username, ret[3], method,
                                            headers=ret[2])
            else:
                logging.info(dict(error='otp token omitted', **logmsg))
                return dict(message=_(u'access denied')), 403
        elif not method or method == 'local':
            ret = local_func.login(username, password)
            if ret[1] != 200:
                return ret
            return self._login_accepted(username, ret[2], 'local')
        elif method in self.config.AUTH_PARAMS.keys():
            return oauth2_func.login(self.oauth, method, cache=Ocache())
        else:
            msg = _(u'unsupported login method')
            logging.error(dict(message=msg, **logmsg))
            return dict(message=msg), 500

    def _login_accepted(self, username, account, method, headers=None):
        """Login accepted from provider: create a session

        Args:
          username (str): the account's unique username
          account (obj): account object in database
          method (str): method, e.g. local or google
          headers (dict): additional headers, such as Set-Cookie
        """
        account.last_login = utcnow()
        account.invalid_attempts = 0
        try:
            g.db.commit()
        except Exception as ex:
            return db_abort(str(ex), action='_login_accepted')

        # connexion doesn't support cookie auth. probably just as well,
        #  this forced me to implement a JWT design with nonce token
        # https://github.com/zalando/connexion/issues/791
        #  TODO come up with a standard approach, this is still janky
        #  and does not do signature validation (let alone PKI)

        # TODO research concerns raised in:
        # https://paragonie.com/blog/2017/03/jwt-json-web-tokens-is-bad-
        #  standard-that-everyone-should-avoid
        acc = AccessControl()
        logmsg = dict(action='login', username=username, uid=account.uid,
                      method=method, account_id=account.id)
        duration = (self.login_admin_limit if account.is_admin
                    else self.login_session_limit)
        if (account.password_must_change and method == 'local'):
            roles = ['person', 'pwchange']
            duration = 300
        elif not account.totp and self.config.LOGIN_MFA_REQUIRED and (
                method == 'local' or self.config.LOGIN_MFA_EXTERNAL):
            roles = ['mfarequired']
            duration = 300
        elif not self.totp_bypass(account.uid) and account.totp and (
                method == 'local' or self.config.LOGIN_MFA_EXTERNAL) and not (
                    acc.auth and 'pendingtotp' in acc.auth):
            roles = ['pendingtotp']
            logmsg['action'] = 'totp_challenge'
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
        if acc.apikey_id:
            logmsg['apikey'] = acc.apikey_id
        logging.info(logmsg)
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
                return retval, 201, headers
            else:
                return redirect('%s%s?token=%s' % (
                    account.settings.url,
                    self.config.AUTH_LANDING_PAGE, retval['jwt_token']))
        else:
            return db_abort(_(u'login session trouble'), action='login')

    def totp_bypass(self, uid):
        """Check for bypass cookie

        Args:
          uid (str): User ID
        Returns:
          bool: valid bypass found
        """
        if request.cookies and (self.config.LOGIN_MFA_COOKIE_NAME
                                in request.cookies):
            if g.session.get(
                    uid, request.cookies[self.config.LOGIN_MFA_COOKIE_NAME]):
                return True
        return False

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
