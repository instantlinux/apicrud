"""auth controller

created 6-apr-2019 by richb@instantlinux.net
"""

from flask import g, request
import logging

from apicrud.session_auth import SessionAuth
from apicrud import singletons
import config
import models


class AuthController(object):

    def __init__(self):
        self.resource = 'auth'
        if self.resource not in singletons.controller:
            singletons.controller[self.resource] = self

    @staticmethod
    def login(body):
        return SessionAuth(config=config, models=models).account_login(
            body['username'], body['password'], roles_from=models.List)

    def logout():
        creds = request.authorization
        if creds:
            g.session.delete(creds.username, creds.password)
            logging.info('action=logout id=%s' % creds.username)
        return dict(message='logged out'), 200
