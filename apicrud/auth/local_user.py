"""local_user

created 26-mar-2020 by richb@instantlinux.net
monolith broken out 6-apr-2021
"""
from flask import g, request
from flask_babel import _
import logging
from passlib.hash import sha256_crypt
from sqlalchemy import or_
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm.exc import NoResultFound
import string

from .. import SessionAuth
from ..utils import gen_id, identity_normalize
from ..messaging.confirmation import Confirmation


class LocalUser(SessionAuth):
    """Manage local user accounts

    Args:
      func_send(function): name of function for sending message
    """
    def __init__(self, func_send=None):
        super().__init__(func_send=func_send)

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
