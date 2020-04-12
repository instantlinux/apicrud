"""auth.py

Support openapi securitySchemes: basic_auth and api_key endpoints

created 25-mar-2019 by richb@instantlinux.net
"""

from datetime import datetime
from flask import g
import logging


def basic_auth(username, password, required_scopes=None):
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
