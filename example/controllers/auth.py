"""auth controller

created 6-apr-2019 by richb@instantlinux.net
"""

from flask import g, request
import logging

from apicrud.session_auth import SessionAuth
from apicrud import singletons
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
          body (dict): specify username and password
        Returns:
          dict:
            Fields include jwt_token (contains uid / account ID),
            ID of entry in settings database, and a sub-dictionary
            with mapping of endpoints registered to microservices
        """
        return SessionAuth(models=models).account_login(
            body['username'], body['password'], roles_from=models.List)

    def logout():
        """Logout

        Returns:
          tuple: dict with message and http status code 200
        """
        creds = request.authorization
        if creds:
            g.session.delete(creds.username, creds.password)
            logging.info('action=logout id=%s' % creds.username)
        return dict(message='logged out'), 200
