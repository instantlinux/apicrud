"""oauth2

created 26-mar-2021 by richb@instantlinux.net
"""
from flask import g
from flask_babel import _
import logging
from sqlalchemy.orm.exc import NoResultFound
import string

from .. import state
from ..database import db_abort
from ..metrics import Metrics
from ..session_auth import SessionAuth
from ..utils import gen_id, identity_normalize


class OAuth2(SessionAuth):
    """OAuth2 for Session Authorization
    """
    def __init__(self):
        super().__init__()
        self.func_send = state.func_send

    def callback(self, method, code=None, state=None):
        """Callback from 3rd-party OAuth2 provider auth

        Parse the response, look up the account based on email
        address, and pass control to SessionAuth.login_accepted

        Args:
          method (str): provider name, such as google
          code (str): validation code from provider
          state (str): provider state
        """
        client = self.oauth.create_client(method)
        logmsg = dict(action='oauth_callback', method=method)
        if not client:
            msg = _(u'login client missing')
            logging.error(dict(message=msg, **logmsg))
            return dict(message=msg), 405
        try:
            token = client.authorize_access_token(
                redirect_uri='%s%s/%s/%s' % (self.config.PUBLIC_URL,
                                             self.config.BASE_URL,
                                             'auth_callback', method))
        except Exception as ex:
            msg = _(u'openid client failure')
            logging.warning(dict(message=msg, error=str(ex), **logmsg))
            return dict(message=msg), 405
        if 'id_token' in token:
            user = client.parse_id_token(token)
        else:
            user = client.userinfo()
        if method == 'slack':
            user = user['user']
        identity = identity_normalize(user.get('email'))
        if not identity or '@' not in identity:
            logging.warning(dict(message='identity missing', usermeta=user,
                                 **logmsg))
            return dict(message=_(u'access denied')), 403
        try:
            account = g.db.query(self.models.Account).join(
                self.models.Person).filter(
                    self.models.Person.identity == identity,
                    self.models.Account.status == 'active').one()
            username = account.name
        except NoResultFound:
            account = None
        except Exception as ex:
            return db_abort(str(ex), **logmsg)
        if not account:
            try:
                account = g.db.query(self.models.Account).join(
                    self.models.Person).join(self.models.Contact).filter(
                    self.models.Contact.info == identity,
                    self.models.Contact.type == 'email',
                    self.models.Contact.status == 'active',
                    self.models.Account.status == 'active').one()
                username = account.name
            except NoResultFound:
                return self._handle_unknown_user(method, user)
        logging.info(dict(usermeta=user, **logmsg))
        return self.login_accepted(username, account, method)

    def _handle_unknown_user(self, method, usermeta):
        """Handle unknown external user access based on configured
        LOGIN_EXTERNAL_POLICY.

        Args:
          method (str): login method, as in 'google'
          usermeta (dict): the metadata object from external provider
        """
        identity = identity_normalize(usermeta.get('email'))
        name = usermeta.get('name')
        picture = usermeta.get('picture') or usermeta.get('avatar_url')
        if not picture and usermeta.get('gravatar_id'):
            picture = 'https://2.gravatar.com/avatar/%s' % usermeta.get(
                'gravatar_id')
        username = '%s-%s' % (
            identity.split('@')[0][:15],
            gen_id(length=6, prefix='',
                   chars=string.digits + string.ascii_lowercase))
        logmsg = dict(action='login', method=method, identity=identity)

        if self.config.LOGIN_EXTERNAL_POLICY == 'closed':
            msg = _(u'not valid')
            logging.info(dict(msg=msg, **logmsg))
            Metrics().store('logins_fail_total')
            return dict(message=msg), 403
        elif self.config.LOGIN_EXTERNAL_POLICY == 'auto':
            ret = self.register(identity, username, name, picture=picture,
                                template=None)
            if ret[1] != 200:
                return ret
            ret = self.account_add(username, uid=ret[0]['uid'])
            if ret[1] != 201:
                return ret
            account = g.db.query(self.models.Account).filter_by(
                id=ret[0]['id']).one()
            return self.login_accepted(username, account, method)
        elif self.config.LOGIN_EXTERNAL_POLICY == 'open':
            ret = self.register(identity, username, name, picture=picture)
            if ret[1] != 200:
                return ret
            ret2 = self.account_add(username, uid=ret[0]['uid'])
            return ret2 if ret2 == 201 else ret

        # TODO LOGIN_EXTERNAL_POLICY == 'onrequest'
        return dict(message='unimplemented'), 403
