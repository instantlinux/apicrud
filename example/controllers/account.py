"""account controller

created 31-mar-2019 by richb@instantlinux.net
"""

from flask import g, request
from sqlalchemy.orm.exc import NoResultFound

from apicrud.basic_crud import BasicCRUD
import i18n_textstrings as i18n
from apicrud.session_auth import SessionAuth
from apicrud import singletons

from messaging import send_contact
from models import Settings


class AccountController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='account')

    @staticmethod
    def create(body):
        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        return self._create(body)

    def _create(self, body, identity=None):
        try:
            body['settings_id'] = g.db.query(
                Settings).filter_by(name='global').one().id
        except NoResultFound:
            return dict(message='failed to read global settings'), 405
        body['password'] = ''
        body['password_must_change'] = True
        retval = super(AccountController, AccountController).create(body)
        if retval[1] != 201:
            return retval
        retval[0]['uid'] = body.get('uid')
        return retval

    @staticmethod
    def change_password(uid, body):
        """Change password

        Args:
          body (dict):
            Fields new_password, verify_password are required;
            either the old_password or a reset_token can be used
            to authorized the request.
        Returns:
          tuple: dict with account_id/uid/username, http response
        """
        if (not body.get('new_password') or
                body.get('new_password') != body.get('verify_password')):
            return dict(message='passwords do not match'), 405
        return SessionAuth(func_send=send_contact.delay).change_password(
            uid, body.get('new_password'), body.get('reset_token'),
            old_password=body.get('old_password'))

    @staticmethod
    def get_password(uid):
        """Dummy get_password function is needed for react-admin's
        edit workflow (a get must precede put)

        Args:
          uid (str): User ID
        """
        self = singletons.controller.get('account')
        try:
            account = g.db.query(self.model).filter_by(
                uid=uid, status='active').one()
        except NoResultFound:
            return dict(id=uid, message='account not found'), 404
        return dict(id=uid, username=account.name), 200

    @staticmethod
    def register(body):
        """Register a new account

        Args:
          body (dict):
            If forgot_password is set, send an email with reset token.
            Otherwise examine username, identity (email address) and
            name fields. Reject the new account if a duplicate identity
            or username already exists. Otherwise add the new account
            with Person and primary Contact objects. Finally send
            a confirmation email to the primary contact address.
        Returns:
          tuple: id of account created, and http status
        """

        self = singletons.controller.get('account')
        if body.get('forgot_password'):
            return SessionAuth(func_send=send_contact.delay).forgot_password(
                    body.get('identity'), body.get('username'))
        retval = SessionAuth(func_send=send_contact.delay).register(
            body.get('identity'), body.get('username'), body.get('name'),
            i18n_id=i18n.PASSWORD_RESET)
        if retval[1] > 201:
            return retval
        body['identity'] = body.get('identity').lower()
        return self._create(dict(uid=retval[0]['uid'], name=body['username'],
                                 status='active'))
