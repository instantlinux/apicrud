"""account controller

created 31-mar-2019 by richb@instantlinux.net
"""

from flask import g
from flask_babel import _
from sqlalchemy.orm.exc import NoResultFound

from apicrud import BasicCRUD, SessionAuth, state
from apicrud.auth import LocalUser


class AccountController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='account')

    @staticmethod
    def create(body):
        return SessionAuth().account_add(body.get('identity'),
                                         body.get('uid'))

    @staticmethod
    def change_password(uid, body):
        """Change password

        Args:
          body (dict):
            Fields new_password, verify_password are required;
            either the old_password or a reset_token can be used
            to authorize the request.
        Returns:
          tuple: dict with account_id/uid/username, http response
        """
        return LocalUser().change_password(
            uid, body.get('new_password'), body.get('reset_token'),
            old_password=body.get('old_password'),
            verify_password=body.get('verify_password'))

    @staticmethod
    def get_password(uid):
        """Dummy get_password function is needed for react-admin's
        edit workflow (a get must precede put)

        Args:
          uid (str): User ID
        """
        self = state.controllers.get('account')
        try:
            account = g.db.query(self.model).filter_by(
                uid=uid, status='active').one()
        except NoResultFound:
            return dict(id=uid, message=_(u'account not found')), 404
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
        if body.get('forgot_password'):
            return LocalUser().forgot_password(
                    body.get('identity'), body.get('username'))
        retval = LocalUser().register(
            body.get('identity'), body.get('username'), body.get('name'))
        if retval[1] > 201:
            return retval
        return SessionAuth().account_add(body['username'], retval[0]['uid'])
