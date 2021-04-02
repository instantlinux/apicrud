"""auth controller

created 6-apr-2019 by richb@instantlinux.net
"""

from flask import g, request
from flask_babel import _
import logging

from apicrud import SessionAuth, singletons
from messaging import send_contact
import models


class AuthController(object):

    def __init__(self):
        self.resource = 'auth'
        if self.resource not in singletons.controller:
            singletons.controller[self.resource] = self

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
        return SessionAuth(roles_from=models.List).account_login(
            body.get('username'), body.get('password'),
            method=body.get('method', 'local'))

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
        return SessionAuth(func_send=send_contact.delay,
                           roles_from=models.List).oauth_callback(
                               method, code=code, state=state)

    @staticmethod
    def auth_params():
        """Get authorizaion info"""
        return SessionAuth().auth_params()

    @staticmethod
    def find():
        """Find auth methods - for the frontend's Login screen"""
        return SessionAuth().methods()
