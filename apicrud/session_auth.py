"""session_auth

created 26-mar-2020 by richb@instantlinux.net
"""
from flask import g, redirect, request
from flask_babel import _
import jwt
import logging
import os
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm.exc import NoResultFound
import time

from . import state
from .access import AccessControl
from .account_settings import AccountSettings
from .const import Constants
from .database import db_abort
from .messaging.confirmation import Confirmation
from .metrics import Metrics
from .ratelimit import RateLimit
from .service_config import ServiceConfig
from .service_registry import ServiceRegistry
from .utils import gen_id, identity_normalize, utcnow

OC = {}


class SessionAuth(object):
    """Session Authorization

    Functions for login, password and role authorization

    Args:
      roles_from (obj): model for which to look up authorizations
    """

    def __init__(self, roles_from=None):
        config = self.config = ServiceConfig().config
        self.jwt_secret = config.JWT_SECRET
        self.login_session_limit = config.LOGIN_SESSION_LIMIT
        self.login_admin_limit = config.LOGIN_ADMIN_LIMIT
        self.func_send = state.func_send
        self.models = state.models
        self.oauth = state.oauth['init']
        self.roles_from = roles_from
        self.redis_conn = state.redis_conn

    def account_login(self, username, password, method=None, otp=None,
                      nonce=None):
        """Log in using local or OAuth2 credentials

        Args:
          username (str): account name or email
          password (str): credential
          method (str): local, ldap, or google / facebook / twitter etc
          otp (str): one-time or backup password
          nonce (str): a nonce check value (for OAuth2: optional)

        Returns:
          dict:
            Fields include jwt_token (contains uid / account ID),
            ID of entry in settings database, and a sub-dictionary
            with mapping of endpoints registered to microservices
        """
        from .auth import ldap_func, local_func, oauth2_func, totp_func

        logmsg = dict(action='login', username=username, method=method)
        acc = AccessControl()
        content, status, headers = _(u'access denied'), 403, []
        if RateLimit(enable=True,
                     interval=self.config.LOGIN_LOCKOUT_INTERVAL).call(
                         limit=self.config.LOGIN_ATTEMPTS_MAX,
                         service='login.attempt', uid=username):
            time.sleep(5)
            msg = _(u'locked out')
            logging.warning(dict(message=msg, **logmsg))
            return dict(username=username, message=msg), 403
        if acc.auth and ('pendingtotp' in acc.auth or (otp and acc.apikey_id)):
            # TODO make this pendingtotp finite-state logic more robust
            if otp:
                content, status, headers, account = totp_func.login(
                    username, otp, redis_conn=self.redis_conn)
                if status == 200:
                    content, status, headers = self.login_accepted(
                        username, account, acc.auth_method, headers=headers)
            else:
                logging.info(dict(error='otp token omitted', **logmsg))
        elif method in self.config.AUTH_PARAMS.keys():
            content, status = oauth2_func.login(self.oauth, method,
                                                nonce=nonce)
        elif not method or method in self.config.AUTH_METHODS:
            items = method if method else self.config.AUTH_METHODS
            for item in items:
                if item == 'local':
                    content, status, account = local_func.login(username,
                                                                password)
                elif item == 'ldap':
                    content, status, account = ldap_func.login(username,
                                                               password)
                if status == 200:
                    method = item
                    break
            if status == 200:
                content, status, headers = self.login_accepted(
                    username, account, method)
        else:
            msg = _(u'unsupported login method')
            logging.error(dict(message=msg, **logmsg))
            return dict(message=msg), 500
        if status in (200, 201):
            RateLimit().reset(service='login.attempt', uid=username)
        else:
            Metrics().store('logins_fail_total', labels=['method=%s' % method])
        return content, status, headers

    def login_accepted(self, username, account, method, headers=None):
        """Login accepted from provider: create a session

        Args:
          username (str): the account's unique username
          account (obj): account object in database
          method (str): method, e.g. local or google
          headers (dict): additional headers, such as Set-Cookie
        """
        account.last_login = utcnow()

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
                method in ('local', 'ldap') or self.config.LOGIN_MFA_EXTERNAL):
            roles = ['mfarequired']
            duration = 300
        elif not self.totp_bypass(account.uid) and account.totp and (
                method in ('local', 'ldap') or
                self.config.LOGIN_MFA_EXTERNAL) and not (
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
                roles += self.get_roles(account.uid,
                                        member_model=self.roles_from)
        else:
            roles = []
        if acc.apikey_id:
            logmsg['apikey'] = acc.apikey_id
        logging.info(logmsg)
        ses = g.session.create(account.uid, roles, acc=account.id,
                               identity=account.owner.identity,
                               method=method, ttl=duration)
        if ses:
            retval = dict(
                jwt_token=jwt.encode(
                    ses, self.jwt_secret, algorithm='HS256'),
                resources=ServiceRegistry().find()['url_map'],
                settings_id=account.settings_id, username=account.name)
            if hasattr(account.settings, 'default_storage_id'):
                retval['storage_id'] = account.settings.default_storage_id
            if 'pendingtotp' not in roles:
                Metrics().store('logins_success_total', labels=['method=%s' %
                                                                method])
            if method in ('local', 'ldap'):
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

    def register(self, identity, username, name, template='confirm_new',
                 picture=None):
        """Register a new account: create related records in database
        and send confirmation token to new user

        TODO caller still has to invoke account_add function to
        generate record in accounts table

        Args:
          identity (str): account's primary identity, usually an email
          username (str): account's username
          name (str): name
          picture (url): URL of an avatar / photo
          template (str): template for message (confirming new user)
        Returns:
          tuple: the Confirmation.request dict and http response
        """
        if not username or not identity or not name:
            return dict(message=_(u'all fields required')), 400
        identity = identity_normalize(identity)
        logmsg = dict(action='register', identity=identity,
                      username=username)
        try:
            g.db.query(self.models.Account).filter_by(name=username).one()
            msg = _(u'that username is already registered')
            logging.warning(dict(message=msg, **logmsg))
            return dict(message=msg), 405
        except NoResultFound:
            pass
        uid = None
        try:
            existing = g.db.query(self.models.Person).filter_by(
                identity=identity).one()
            uid = existing.id
            g.db.query(self.models.Account).filter_by(uid=uid).one()
            msg = _(u'that email is already registered, use forgot-password')
            logging.warning(dict(message=msg, **logmsg))
            return dict(message=msg), 405
        except NoResultFound:
            pass
        if uid:
            try:
                cid = g.db.query(self.models.Contact).filter_by(
                    info=identity, type='email').one().id
            except Exception as ex:
                msg = 'registration trouble, error=%s' % str(ex)
                logging.error(dict(message=msg, **logmsg))
                return dict(message=msg), 405
        else:
            person = self.models.Person(
                id=gen_id(prefix='u-'), name=name, identity=identity,
                status='active')
            uid = person.id
            cid = gen_id()
            g.db.add(person)
            g.db.add(self.models.Contact(id=cid, uid=uid, type='email',
                                         info=identity))
            g.db.commit()
            logging.info(dict(message=_(u'person added'), uid=uid, **logmsg))
        # If browser language does not match global default language, add
        # a profile setting
        lang = request.accept_languages.best_match(self.config.LANGUAGES)
        try:
            default_lang = g.db.query(self.models.Settings).filter_by(
                name='global').one().lang
        except Exception:
            default_lang = 'en'
        if lang and lang != default_lang:
            try:
                g.db.add(self.models.Profile(id=gen_id(), uid=uid, item='lang',
                                             value=lang, status='active'))
                g.db.commit()
            except IntegrityError:
                # Dup entry from previous attempt
                g.db.rollback()
        if picture:
            try:
                g.db.add(self.models.Profile(
                    id=gen_id(), uid=uid, item='picture', value=picture,
                    status='active'))
                g.db.commit()
            except (DataError, IntegrityError):
                # Dup entry from previous attempt or value too long
                g.db.rollback()
        if template:
            return Confirmation().request(cid, template=template)
        else:
            try:
                g.db.query(self.models.Contact).filter_by(
                    id=cid).one().status = 'active'
                g.db.commit()
            except Exception as ex:
                return db_abort(str(ex), rollback=True,
                                msg=_(u'contact activation problem'), **logmsg)
            return dict(uid=uid, message='registered'), 200

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
        return dict(id=account.id, uid=uid, username=username), 201

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
        if 'local' not in self.config.AUTH_METHODS:
            internal_policy = 'closed'
        ret = []
        for method in self.config.AUTH_METHODS:
            if method == 'oauth2':
                for ext_method in self.config.AUTH_PARAMS.keys():
                    if os.environ.get('%s_CLIENT_ID' % ext_method.upper()):
                        ret.append(ext_method)
            else:
                ret.append(method)
        return dict(
            items=ret, count=len(ret),
            policies=dict(
                login_internal=internal_policy,
                login_external=self.config.LOGIN_EXTERNAL_POLICY)), 200

    def get_roles(self, uid, member_model=None, resource=None, id=None):
        """Get roles that match uid / id for a resource
        Each is in the form <resource>-<id>-<privacy level>

        Args:
          uid (str): User ID
          member_model (str): resource-name of DB model that defines
            membership in resource
          resource (str): the resource that defines privacy (e.g. list)
          id (str): ID of the resource (omit if all are desired)
        Returns:
          list of str: authorized roles
        """
        acc = AccessControl()
        # TODO improve defaulting of member_model and resource from
        #  rbac.yaml
        resource = resource or acc.primary_resource
        if not member_model and len(state.private_res):
            member_model = state.private_res[0].get('resource')
        if not resource or not member_model:
            return []
        column = '%s_id' % resource
        try:
            query = g.db.query(getattr(
                self.models, member_model.capitalize())).filter_by(
                    uid=uid, status='active')
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

    def update_auth(self, id, member_model=None, resource=None, force=False):
        """Check current access, update if recently changed

        Args:
          id (str): resource id of parent resource
          resource (str):
            parent resource for which membership should be checked
          force (bool): perform update regardless of logged-in permissions
        """
        acc = AccessControl()
        resource = resource or acc.primary_resource
        current = set(acc.auth)
        if force or ('%s-%s-%s' % (resource, id, Constants.AUTH_INVITEE)
                     not in current):
            # TODO handle privilege downgrade member/host->invitee
            current |= set(self.get_roles(acc.uid, member_model=member_model,
                                          resource=resource, id=id))
            creds = request.authorization
            g.session.update(creds.username, creds.password, 'auth',
                             ':'.join(current))
