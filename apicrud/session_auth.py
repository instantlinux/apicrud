"""session_auth

created 26-mar-2020 by richb@instantlinux.net
"""
from datetime import datetime, timedelta
from flask import g, request
from flask_babel import _
import jwt
import logging
from passlib.hash import sha256_crypt
from redis.exceptions import ConnectionError
from sqlalchemy import or_
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy_utils.types.encrypted.padding import InvalidPaddingError
import string
import time

from .access import AccessControl
from .const import Constants
from .messaging.confirmation import Confirmation
from .metrics import Metrics
from .service_config import ServiceConfig
from .service_registry import ServiceRegistry
from .utils import gen_id, utcnow

APIKEYS = {}


class SessionAuth(object):
    """Session Authorization

    Functions for login, password and role authorization

    Args:
      func_send(function): name of function for sending message
    """

    def __init__(self, func_send=None):
        config = self.config = ServiceConfig().config
        self.models = ServiceConfig().models
        self.jwt_secret = config.JWT_SECRET
        self.login_attempts_max = config.LOGIN_ATTEMPTS_MAX
        self.login_lockout_interval = config.LOGIN_LOCKOUT_INTERVAL
        self.login_session_limit = config.LOGIN_SESSION_LIMIT
        self.login_admin_limit = config.LOGIN_ADMIN_LIMIT
        self.func_send = func_send

    def account_login(self, username, password, roles_from=None):
        """ Log in with username or email

        Args:
          username (str): account name or email
          password (str): credential
          identity_from (obj):  model from which to find contact info
          roles_from (obj): model for which to look up authorizations

        Returns:
          dict:
            Fields include jwt_token (contains uid / account ID),
            ID of entry in settings database, and a sub-dictionary
            with mapping of endpoints registered to microservices
        """

        metrics = Metrics()
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
        except NoResultFound:
            return dict(username=username, message='not valid'), 403
        except OperationalError as ex:
            logging.error('action=login message=%s' % str(ex))
            return dict(message=_(u'DB operational error, try again')), 403
        if (account.invalid_attempts >= self.login_attempts_max and
            account.last_invalid_attempt + timedelta(
                seconds=self.login_lockout_interval) > datetime.utcnow()):
            time.sleep(5)
            metrics.store('logins_fail_total')
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
        logging.info('action=login username=%s account_id=%s' %
                     (username, account.id))
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
        if (account.password_must_change):
            roles = ['person', 'pwchange']
        # TODO parameterize model name contact
        elif (g.db.query(self.models.Contact).filter(
                self.models.Contact.info == account.owner.identity,
                self.models.Contact.type == 'email'
                ).one().status == 'active'):
            roles = ['admin', 'user'] if account.is_admin else ['user']
            if roles_from:
                roles += self.get_roles(account.uid, roles_from)
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
            metrics.store('logins_success_total')
            return retval, 201
        else:
            return dict(message=_(u'DB operational error')), 500

    def api_access(self, apikey, roles_from=None):
        """ Access using API key

        Args:
          apikey (str): the API key
          roles_from (obj): model for which to look up authorizations

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
            if roles_from:
                APIKEYS[key_id]['roles'] += self.get_roles(uid, roles_from)
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

    def register(self, identity, username, name, template='confirm_new'):
        """Register a new account: create related records in database
        and send confirmation token to new user

        TODO caller still has to invoke account-create function to
        generate record in accounts table

        Args:
          identity (str): account's primary identity, usually an email
          username (str): account's username
          name (str): name
          template (str): template for message (confirming new user)
        Returns:
          tuple: the Confirmation.request dict and http response
        """
        if not username or not identity or not name:
            return dict(message=_(u'all fields required')), 400
        identity = identity.lower()
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
            g.db.add(self.models.Profile(id=gen_id(), uid=uid, item='lang',
                                         value=lang, status='active'))
            g.db.commit()
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
    retval = SessionAuth().api_access(apikey, roles_from=models.List)
    if not retval:
        return retval
    if required_scopes and (set(required_scopes) & set(retval['scopes']) !=
                            set(required_scopes)):
        logging.info(dict(action='api_key', prefix=apikey.split('.')[0],
                          scopes=retval['scopes'], message='denied'))
        return None
    Metrics().store('api_key_auth_total')
    return retval
