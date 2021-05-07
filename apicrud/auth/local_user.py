"""local_user

created 26-mar-2020 by richb@instantlinux.net
monolith broken out 6-apr-2021
"""
from flask import g
from flask_babel import _
import logging
from passlib.hash import sha256_crypt
import redis.exceptions
from sqlalchemy import or_
from sqlalchemy.orm.exc import NoResultFound
import string

from .. import SessionAuth
from ..utils import identity_normalize, utcnow
from ..messaging.confirmation import Confirmation


class LocalUser(SessionAuth):
    """Manage local user accounts
    """
    def __init__(self):
        super().__init__()

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
        or email address. For security, administrators are not allowed
        to use this feature.

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
        return Confirmation().request(id, template=template)

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


# Support openapi securitySchemes: basic_auth endpoint
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
    elif 'exp' in session and utcnow().strftime('%s') > session['exp']:
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
