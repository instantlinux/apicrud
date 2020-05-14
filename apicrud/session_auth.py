"""session_auth

Functions for login, password and role authorization

created 26-mar-2020 by richb@instantlinux.net
"""

from datetime import datetime, timedelta
from flask import g, request
import jwt
import logging
from passlib.hash import sha256_crypt
from sqlalchemy import or_
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.exc import NoResultFound
import string
import time

from .access import AccessControl
from .messaging.confirmation import Confirmation
from . import constants
from .constants import i18n
from .service_registry import ServiceRegistry


class SessionAuth(object):
    def __init__(self, config=None, models=None, func_send=None):
        self.config = config
        self.models = models
        self.jwt_secret = config.JWT_SECRET
        self.login_attempts_max = config.LOGIN_ATTEMPTS_MAX
        self.login_lockout_interval = config.LOGIN_LOCKOUT_INTERVAL
        self.login_session_limit = config.LOGIN_SESSION_LIMIT
        self.login_admin_limit = config.LOGIN_ADMIN_LIMIT
        self.func_send = func_send

    def account_login(self, username, password, roles_from=None):
        """ Log in with username or email

        parameters:
          username - account name or email
          password - credential
          identity_from - model from which to find contact info
          roles_from - model for which to look up authorizations
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
        except NoResultFound:
            return dict(username=username, message='not valid'), 403
        except OperationalError as ex:
            logging.error('action=login message=%s' % str(ex))
            return dict(message='DB operational error, try again'), 403
        if (account.invalid_attempts >= self.login_attempts_max and
            account.last_invalid_attempt + timedelta(
                seconds=self.login_lockout_interval) > datetime.utcnow()):
            time.sleep(5)
            return dict(username=username, message='locked out'), 403
        if account.password == '':
            logging.error("username=%s, message='no password'" % username)
            return dict(username=username, message='no password'), 403
        elif not sha256_crypt.verify(password, account.password):
            account.invalid_attempts += 1
            account.last_invalid_attempt = datetime.utcnow()
            logging.info(
                'action=login username=%s credential=invalid attempt=%d' %
                (username, account.invalid_attempts))
            g.db.commit()
            return dict(username=username, message='not valid'), 403
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
                               identity=account.owner.identity,  ttl=duration)
        if ses:
            retval = dict(
                jwt_token=jwt.encode(
                    ses, self.jwt_secret, algorithm='HS256').decode('utf-8'),
                resources=ServiceRegistry(self.config).find()['url_map'],
                settings_id=account.settings_id)
            if hasattr(account.settings, 'default_storage_id'):
                retval['storage_id'] = account.settings.default_storage_id
            return retval, 201
        else:
            return dict(message='rejected'), 403

    def change_password(self, uid, new_password, reset_token,
                        old_password=None):
        try:
            account = g.db.query(self.models.Account).filter_by(
                uid=uid, status='active').one()
        except NoResultFound:
            return dict(uid=uid, message='account not found'), 404
        logmsg = dict(action='change_password', resource='account',
                      username=account.name, uid=uid)

        if self._password_weak(new_password):
            return dict(message='rejected weak password'), 405
        if old_password:
            if not sha256_crypt.verify(old_password, account.password):
                msg = 'invalid credential'
                logging.warning(dict(message=msg, **logmsg))
                return dict(username=account.name, message=msg), 403
        else:
            retval = Confirmation(self.config, self.models).confirm(
                reset_token)
            if retval[1] != 200:
                msg = 'invalid token'
                logging.warning(dict(message=msg, **logmsg))
                return dict(username=account.name, message=msg), 405
        account.password = sha256_crypt.hash(new_password)
        account.password_must_change = False
        g.db.commit()
        logging.info(dict(message='changed', **logmsg))
        return dict(id=account.id, uid=uid, username=account.name), 200

    def forgot_password(self, identity, username):
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
            return dict(message='username or email not found'), 404
        logging.info(logmsg)
        return Confirmation(self.config, self.models).request(
            id, message=i18n.PASSWORD_RESET, func_send=self.func_send)

    def get_roles(self, uid, member_model, resource=None, id=None):
        """Get roles that match uid / id for a resource
        Each is in the form <resource>-<id>-<privacy level>

        params:
          uid - user ID
          member_model - the DB model that defines membership in resource
          resource - the resource that defines privacy (e.g. list)
          id - ID of the resource (omit if all are desired)
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

        params:
          member_model - model (e.g. Guest) which defines membership in
            resource
          id - resource id of parent resource
          resource - parent resource for which membership should be checked
        """
        acc = AccessControl()
        if not resource:
            resource = acc.primary_res
        current = set(acc.auth)
        if force or ('%s-%s-%s' % (resource, id, constants.AUTH_INVITEE)
                     not in current):
            # TODO handle privilege downgrade member/host->invitee
            current |= set(self.get_roles(acc.uid, member_model,
                                          resource=resource, id=id))
            creds = request.authorization
            g.session.update(creds.username, creds.password, 'auth',
                             ':'.join(current))

    @staticmethod
    def _password_weak(password):
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
            g.session.delete(username, password)
        return None
    return {'uid': username}


def api_key(token, required_scopes=None):
    logging.info('action=api_key token=%s' % token)
    return {'sub': 'user1', 'scope': ''}
