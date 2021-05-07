"""auth controller

created 6-apr-2019 by richb@instantlinux.net
"""

from flask import g, request
from flask_babel import _
import logging

from apicrud import SessionAuth, state
from apicrud.auth import AuthTOTP, OAuth2


class AuthController(object):

    def __init__(self):
        self.resource = 'auth'
        if self.resource not in state.controllers:
            state.controllers[self.resource] = self

    @staticmethod
    def login(body):
        """Login a new session

        Args:
          body (dict): specify method, or username and password
        Returns:
          dict:
            Fields include jwt_token (contains uid / account ID),
            ID of entry in settings database, and a sub-dictionary
            with mapping of endpoints registered to microservices
        """
        return SessionAuth().account_login(
            body.get('username'), body.get('password'),
            method=body.get('method'), otp=body.get('otp'),
            nonce=body.get('nonce'))

    def logout():
        """Logout

        Returns:
          tuple: dict with message and http status code 200
        """
        creds = request.authorization
        if creds:
            g.session.delete(creds.username, creds.password)
            logging.info('action=logout id=%s' % creds.username)
        return dict(message=_(u'logged out')), 200

    @staticmethod
    def auth_callback(method, code, state):
        return OAuth2().callback(method, code=code, state=state)

    @staticmethod
    def auth_params():
        """Get authorization info"""
        return SessionAuth().auth_params()

    @staticmethod
    def totp_generate():
        """Generate a new TOTP token"""
        return AuthTOTP().generate()

    @staticmethod
    def totp_register(body):
        """Register TOTP for user"""
        return AuthTOTP().register(body)

    @staticmethod
    def find():
        """Find auth methods - for the frontend's Login screen"""
        return SessionAuth().methods()
