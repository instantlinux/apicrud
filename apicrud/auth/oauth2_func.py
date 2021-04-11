"""oauth2_func

created 29-mar-2021 by richb@instantlinux.net
"""
from flask_babel import _
import logging
from urllib.parse import parse_qs, urlparse

from .. import ServiceConfig


def login(oauth_reg, method, cache=None):
    """Initiate OAuth2 login

    Args:
      oauth_reg (obj): pre-registered oauth object (from initialize.py)
      method (str): provider name
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
                            'auth_callback', method))
        if config.AUTH_SKIP_CORS:
            state = parse_qs(urlparse(retval.location).query).get(
                'state')[0]
            if cache:
                cache.set('session_foo_state', state, expires=120)
        if retval.status_code == 302:
            return dict(location=retval.location), 200
    except RuntimeError as ex:
        error = str(ex)
    logging.error(dict(message=msg, error=error, **logmsg))
    return dict(message=msg), 405
