"""session_auth

created 26-mar-2020 by richb@instantlinux.net
"""
from datetime import datetime, timedelta
from flask import g, redirect, request, session as flask_session
from flask_babel import _
import jwt
import logging
import os
from passlib.hash import sha256_crypt
from redis.exceptions import ConnectionError
from sqlalchemy import or_
from sqlalchemy.exc import DataError, IntegrityError, OperationalError
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy_utils.types.encrypted.padding import InvalidPaddingError
import string
import time
from urllib.parse import parse_qs, urlparse

from .access import AccessControl
from .account_settings import AccountSettings
from .const import Constants
from .initialize import oauth
from .messaging.confirmation import Confirmation
from .metrics import Metrics
from .service_config import ServiceConfig
from .service_registry import ServiceRegistry
from .utils import gen_id, utcnow, identity_normalize

APIKEYS = {}
OC = {}


class Ocache(object):
    def __init__(self):
        """TODO this goes away when OAuth2 debugging is done"""
        if 'cache' not in OC:
            OC['cache'] = {}
        self.cache = OC['cache']

    def set(self, key, value, expires=None):
        self.cache[key] = value

    def get(self, key):
        return self.cache.get(key)


class SessionAuth(object):
    """Session Authorization

    Functions for login, password and role authorization

    Args:
      func_send(function): name of function for sending message
      roles_from (obj): model for which to look up authorizations
    """

    def __init__(self, func_send=None, roles_from=None):
        config = self.config = ServiceConfig().config
        self.models = ServiceConfig().models
        self.jwt_secret = config.JWT_SECRET
        self.login_attempts_max = config.LOGIN_ATTEMPTS_MAX
        self.login_lockout_interval = config.LOGIN_LOCKOUT_INTERVAL
        self.login_session_limit = config.LOGIN_SESSION_LIMIT
        self.login_admin_limit = config.LOGIN_ADMIN_LIMIT
        self.func_send = func_send
        self.oauth = oauth['init']
        self.roles_from = roles_from

    def account_login(self, username, password, method='local'):
        """Log in using local or OAuth2 credentials

        Args:
          username (str): account name or email
          password (str): credential
          method (str): local, or google / facebook / twitter etc

        Returns:
          dict:
            Fields include jwt_token (contains uid / account ID),
            ID of entry in settings database, and a sub-dictionary
            with mapping of endpoints registered to microservices
        """
        if not method or method == 'local':
            return self._login_local(username, password)
        elif method in self.config.AUTH_PARAMS.keys():
            logmsg = dict(action='account_login', method=method)
            try:
                client = self.oauth.create_client(method)
            except RuntimeError as ex:
                msg = _(u'login client missing')
                logging.error(dict(message=msg, error=str(ex), **logmsg))
                return dict(message=msg), 405
            msg, error = _(u'openid client failure'), ''
            try:
                retval = client.authorize_redirect(
                    '%s%s/%s/%s' % (self.config.PUBLIC_URL,
                                    self.config.BASE_URL,
                                    'auth_callback', method))
                if self.config.AUTH_SKIP_CORS:
                    state = parse_qs(urlparse(retval.location).query).get(
                        'state')[0]
                    Ocache().set('session_foo_state', state, expires=120)
                if retval.status_code == 302:
                    return dict(location=retval.location), 200
            except RuntimeError as ex:
                error = str(ex)
            logging.error(dict(message=msg, error=error, **logmsg))
            return dict(message=msg), 405
        else:
            msg = _(u'unsupported login method')
            logging.error(dict(message=msg, **logmsg))
            return dict(message=msg), 405

    def _login_local(self, username, password):
        """Login using credentials stored in local database

        Args:
          username (str): the username or email identity
          password (str): password
        """
        try:
            if '@' in username:
                account = g.db.query(self.models.Account).join(
                    self.models.Person).filter(
                        self.models.Person.identity == username,
                        self.models.Account.status == 'active').one()
                username = account.name
            else:
                account = g.db.query(self.models.Account).filter_by(
                    name=username, status='active').one()
        except InvalidPaddingError:
            logging.error('action=login message="invalid DB_AES_SECRET"')
            return dict(message=_(u'DB operational error')), 503
        except (NoResultFound, TypeError):
            return dict(username=username, message='not valid'), 403
        except OperationalError as ex:
            logging.error('action=login message=%s' % str(ex))
            return dict(message=_(u'DB operational error, try again')), 500
        if (account.invalid_attempts >= self.login_attempts_max and
            account.last_invalid_attempt + timedelta(
                seconds=self.login_lockout_interval) > datetime.utcnow()):
            time.sleep(5)
            Metrics().store('logins_fail_total')
            return dict(username=username, message=_(u'locked out')), 403
        if account.password == '':
            logging.error("username=%s, message='no password'" % username)
            return dict(username=username, message=_(u'no password')), 403
        elif not sha256_crypt.verify(password, account.password):
            account.invalid_attempts += 1
            account.last_invalid_attempt = datetime.utcnow()
            logging.info(
                'action=login username=%s credential=invalid attempt=%d' %
                (username, account.invalid_attempts))
            g.db.commit()
            return dict(username=username, message=_(u'not valid')), 403

        return self._login_accepted(username, account, 'local')

    def oauth_callback(self, method, code=None, state=None):
        """Callback from 3rd-party OAuth2 provider auth

        Parse the response, look up the account based on email
        address, and proceed if login_accepted

        Args:
          method (str): provider name, such as google
          code (str): validation code from provider
          state (str): provider state
        """
        client = self.oauth.create_client(method)
        logmsg = dict(action='oauth_callback', method=method)
        if not client:
            msg = _(u'login client missing')
            logging.error(dict(message=msg, **logmsg))
            return dict(message=msg), 405
        if self.config.AUTH_SKIP_CORS:
            flask_session['_%s_authlib_state_' % method] = Ocache().get(
                'session_foo_state')
        try:
            token = client.authorize_access_token(
                redirect_uri='%s%s/%s/%s' % (self.config.PUBLIC_URL,
                                             self.config.BASE_URL,
                                             'auth_callback', method))
        except Exception as ex:
            msg = _(u'openid client failure')
            logging.warning(dict(message=msg, error=str(ex),
                                 suggest='for dev: AUTH_SKIP_CORS', **logmsg))
            return dict(message=msg), 405
        if 'id_token' in token:
            user = client.parse_id_token(token)
        else:
            user = client.userinfo()
        identity = identity_normalize(user.get('email'))
        if not identity or '@' not in identity:
            logging.warning(dict(message='identity missing', **logmsg))
            return dict(message=_(u'access denied')), 403
        try:
            account = g.db.query(self.models.Account).join(
                self.models.Person).filter(
                    self.models.Person.identity == identity,
                    self.models.Account.status == 'active').one()
            username = account.name
        except NoResultFound:
            account = None
        except Exception as ex:
            logging.error('action=login message=%s' % str(ex))
            return dict(message=_(u'DB operational error, try again')), 500
        if not account:
            try:
                account = g.db.query(self.models.Account).join(
                    self.models.Person).join(self.models.Contact).filter(
                    self.models.Contact.info == identity,
                    self.models.Contact.type == 'email',
                    self.models.Contact.status == 'active',
                    self.models.Account.status == 'active').one()
                username = account.name
            except NoResultFound:
                return self._handle_unknown_user(method, user)
        logging.info(dict(usermeta=user, **logmsg))
        return self._login_accepted(username, account, method)

    def _login_accepted(self, username, account, method):
        """Login accepted from provider: create a session

        Args:
          username (str): the account's unique username
          account (obj): account object in database
          method (str): method, e.g. local or google
        """
        logging.info('action=login username=%s method=%s account_id=%s' %
                     (username, method, account.id))
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
        if (account.password_must_change and method == 'local'):
            roles = ['person', 'pwchange']
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
        duration = (self.login_admin_limit if account.is_admin
                    else self.login_session_limit)
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
            Metrics().store('logins_success_total')
            if method == 'local':
                return retval, 201
            else:
                return redirect('%s%s?token=%s' % (
                    account.settings.url,
                    self.config.AUTH_LANDING_PAGE, retval['jwt_token']))
        else:
            return dict(message=_(u'DB operational error')), 500

    def _handle_unknown_user(self, method, usermeta):
        """Handle unknown external user access based on configured
        LOGIN_EXTERNAL_POLICY.

        Args:
          method (str): login method, as in 'google'
          usermeta (dict): the metadata object from external provider
        """
        identity = identity_normalize(usermeta.get('email'))
        name = usermeta.get('name')
        picture = usermeta.get('picture') or usermeta.get('avatar_url')
        if not picture and usermeta.get('gravatar_id'):
            picture = 'https://2.gravatar.com/avatar/%s' % usermeta.get(
                'gravatar_id')
        username = '%s-%s' % (
            identity.split('@')[0][:15],
            gen_id(length=6, prefix='',
                   chars=string.digits + string.ascii_lowercase))
        logmsg = dict(action='login', method=method, identity=identity)

        if self.config.LOGIN_EXTERNAL_POLICY == 'closed':
            msg = _(u'not valid')
            logging.info(dict(msg=msg, **logmsg))
            return dict(message=msg), 403
        elif self.config.LOGIN_EXTERNAL_POLICY == 'auto':
            # suppress the registration confirmation email
            # TODO make this configurable
            self.func_send = None
            ret = self.register(identity, username, name, picture=picture)
            if ret[1] != 200:
                return ret
            try:
                g.db.query(self.models.Contact).filter_by(
                    id=ret[0]['id']).one().status = 'active'
                g.db.commit()
            except Exception as ex:
                g.db.rollback()
                msg = _(u'contact activation problem')
                logging.error(dict(msg=msg, error=str(ex), **logmsg))
                return dict(message=msg), 500
            ret = self.account_add(username, uid=ret[0]['uid'])
            if ret[1] != 201:
                return ret
            account = g.db.query(self.models.Account).filter_by(
                id=ret[0]['id']).one()
            return self._login_accepted(username, account, method)
        elif self.config.LOGIN_EXTERNAL_POLICY == 'open':
            ret = self.register(identity, username, name, picture=picture)
            if ret[1] != 200:
                return ret
            ret2 = self.account_add(username, uid=ret[0]['uid'])
            return ret2 if ret2 == 201 else ret

        # TODO onrequest
        return dict(message='unimplemented'), 403

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
            msg = u'failed to read global settings'
            logging.error(dict(message=msg, error=str(ex), **logmsg))
            return dict(message=msg), 500
        account = self.models.Account(
            id=gen_id(), uid=uid, name=username,
            password_must_change=True, password='',
            settings_id=settings_id, status='active')
        try:
            g.db.add(account)
            g.db.commit()
        except Exception as ex:
            msg = _(u'DB operational error')
            logging.error(dict(message=msg, error=str(ex), **logmsg))
            g.db.rollback()
            return dict(message=msg), 500
        return dict(id=account.id, uid=uid), 201

    def api_access(self, apikey):
        """Access using API key

        Args:
          apikey (str): the API key
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
        retval = dict(
            resources=ServiceRegistry().find()['url_map'],
            settings_id=settings.get.id)
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

    def register(self, identity, username, name, template='confirm_new',
                 picture=None):
        """Register a new account: create related records in database
        and send confirmation token to new user

        TODO caller still has to invoke account-create function to
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
        return Confirmation().request(cid, template=template,
                                      func_send=self.func_send)

    def change_password(self, uid, new_password, reset_token,
                        old_password=None, verify_password=None):
        """Update a user's password, applying complexity rules; must
        specify either the old password or a reset token

        Args:
          uid (str): User ID
          new_password (str): the new passphrase
          reset_token (str): a token retrieved from Confirmation.request
          old_password (str): the old passphrase

        Returns:
          tuple: dict with account_id/uid/username, http response
        """

        if not new_password or new_password != verify_password:
            return dict(message=_(u'passwords do not match')), 405
        try:
            account = g.db.query(self.models.Account).filter_by(
                uid=uid, status='active').one()
        except NoResultFound:
            return dict(uid=uid, message=_(u'account not found')), 404
        logmsg = dict(action='change_password', resource='account',
                      username=account.name, uid=uid)

        if self._password_weak(new_password):
            return dict(message=_(u'rejected weak password')), 405
        if old_password:
            if not sha256_crypt.verify(old_password, account.password):
                msg = 'invalid credential'
                logging.warning(dict(message=msg, **logmsg))
                return dict(username=account.name, message=msg), 403
        else:
            retval = Confirmation().confirm(reset_token,
                                            clear_session=True)
            if retval[1] != 200:
                msg = _(u'invalid token')
                logging.warning(dict(message=msg, **logmsg))
                return dict(username=account.name, message=msg), 405
        account.password = sha256_crypt.hash(new_password)
        account.password_must_change = False
        g.db.commit()
        logging.info(dict(message=_(u'changed'), **logmsg))
        return dict(id=account.id, uid=uid, username=account.name), 200

    def forgot_password(self, identity, username, template='password_reset'):
        """Trigger Confirmation.request; specify either the username
        or email address

        Args:
          identity (str): account's primary identity, usually an email
          username (str): account's username
          template (str): template for message (confirming new user)
        Returns:
          tuple: the Confirmation.request dict and http response
        """
        identity = identity_normalize(identity)
        logmsg = dict(action='forgot_password', identity=identity,
                      username=username)
        try:
            account = g.db.query(self.models.Account).join(
                self.models.Person).filter(
                    self.models.Account.is_admin == 0,
                    self.models.Account.status == 'active',
                or_(
                    self.models.Account.name == username,
                    self.models.Person.identity == identity)).one()
            id = g.db.query(self.models.Contact).filter_by(
                type='email', info=account.owner.identity).one().id
        except NoResultFound:
            logging.warning(dict(message='not found', **logmsg))
            if identity and '@' in identity:
                # TODO send reset_invalid message instead of rejection
                return dict(message=_(u'username or email not found')), 404
            return dict(message=_(u'username or email not found')), 404
        logging.info(logmsg)
        return Confirmation().request(
            id, template=template, func_send=self.func_send)

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

    @staticmethod
    def _password_weak(password):
        """Validate password complexity

        Args:
          password (str): Password
        Returns:
          bool: True if at least 3 different types of characters
        """
        return (not set(password).intersection(string.ascii_lowercase),
                not set(password).intersection(string.ascii_uppercase),
                not set(password).intersection(string.digits),
                not set(password).intersection(string.punctuation)
                ).count(True) > 1


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
            except ConnectionError as ex:
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
