"""oauth2_func

created 29-mar-2021 by richb@instantlinux.net
"""
from authlib.integrations.flask_client import OAuth
from flask_babel import _
import logging
import os

from .. import ServiceConfig, state


def login(oauth_reg, method, nonce=None):
    """Initiate OAuth2 login

    Args:
      oauth_reg (obj): pre-registered oauth object (from initialize.py)
      method (str): provider name
      nonce (str): a nonce check value
    """
    logmsg = dict(action='account_login', method=method)
    try:
        client = oauth_reg.create_client(method)
    except RuntimeError as ex:
        msg = _(u'login client missing')
        logging.error(dict(message=msg, error=str(ex), **logmsg))
        return dict(message=msg), 405
    config = ServiceConfig().config
    msg, error = _(u'openid client failure'), ''
    try:
        retval = client.authorize_redirect(
            '%s%s/%s/%s' % (config.PUBLIC_URL,
                            config.BASE_URL,
                            'auth_callback', method), nonce=nonce)
        if retval.status_code == 302:
            return dict(location=retval.location), 200
    except Exception as ex:
        error = str(ex)
    logging.error(dict(message=msg, error=error, **logmsg))
    return dict(message=msg), 405


def oauth2_init(app):
    """Register the OAuth2 providers specified in AUTH_PARAMS config.
    The client-id and client-secret params must be specified as
    environment variables, in the form GOOGLE_CLIENT_ID.

    Args:
      app(obj): the flask object
    """
    state.oauth['init'] = OAuth(app)
    config = ServiceConfig().config
    for provider in config.AUTH_PARAMS.keys():
        client_id = os.environ.get('%s_CLIENT_ID' % provider.upper())
        client_secret = os.environ.get('%s_CLIENT_SECRET' % provider.upper())
        if client_id:
            state.oauth['init'].register(name=provider, client_id=client_id,
                                         client_secret=client_secret,
                                         **config.AUTH_PARAMS[provider])
            logging.info(dict(action='initialize', provider=provider))
