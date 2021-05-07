"""ldap_func

created 4-may-2021 by richb@instantlinux.net
"""
from flask import g
from flask_babel import _
from ldap3 import Connection as LDAPConnection, Server as LDAPServer, \
    ServerPool as LDAPServerPool
from ldap3.core.exceptions import LDAPBindError
import logging
from sqlalchemy.orm.exc import NoResultFound

from .. import state
from ..database import db_abort
from ..service_config import ServiceConfig
from ..utils import identity_normalize, utcnow


def login(username, password):
    """Login using LDAP credentials.  If successful, this passes a
    sqlalchemy account record back for further processing by
    SessionAuth.login_accepted. The email identity is either looked
    up from the LDAP attributes (by default, the attr_identity is
    'mail'), or composed as <attr_name>@<email_domain>.

    Args:
      username (str): the username or email identity
      password (str): password

    Returns:
      tuple: dict with error message, http status (200 if OK), account
    """
    from ..session_auth import SessionAuth

    method = 'ldap'
    config = ServiceConfig().config
    models = state.models
    logmsg = dict(action='login', method=method, username=username)
    bind_dn = username
    if config.LDAP_PARAMS['domain'] and '\\' not in username:
        bind_dn = config.LDAP_PARAMS['domain'] + '\\' + username
    if state.ldap_mock:
        # This is an embarrassing / ugly hack due to absence of support
        # for the bind() call in ldap3 library's MOCK_SYNC feature, along
        # with the difficulty of patching-out the guts of ldap3.Connect
        conn = state.ldap_mock
        if not conn.bind():
            logging.info(dict(credential='invalid', **logmsg))
            return dict(message=_(u'access denied')), 403, None
    else:
        try:
            conn = LDAPConnection(
                state.ldap_serverpool,
                user=bind_dn, password=password, auto_bind=True,
                authentication=config.LDAP_PARAMS['authentication'])
        except LDAPBindError:
            logging.info(dict(credential='invalid', **logmsg))
            return dict(message=_(u'access denied')), 403, None
        except Exception as ex:
            logging.warning(dict(message='LDAP connection failure',
                                 error=str(ex), **logmsg))
            return dict(message=_(u'access denied')), 403, None
    if state.ldap_conn:
        conn.unbind()
        conn = state.ldap_conn
        conn.bind()
    if not conn.search(
            search_base=config.LDAP_PARAMS['search_base'],
            search_filter=config.LDAP_PARAMS['search_filter'].format(
                user=username),
            search_scope='SUBTREE',
            attributes='*',
            get_operational_attributes=True):
        logging.info(dict(message='search failed', **logmsg))
        return dict(message=_(u'access denied')), 403, None
    user = {key: ''.join(val)
            for (key, val) in conn.response[0]['attributes'].items()
            if type(val) is str or type(val[0]) is str}
    account_name = user.get(config.LDAP_PARAMS['attr_name'])
    if config.LDAP_PARAMS['attr_identity']:
        identity = identity_normalize(user.get(
            config.LDAP_PARAMS['attr_identity']))
    else:
        identity = '%s@%s' % (account_name, config.LDAP_PARAMS['email_domain'])
    logmsg['identity'] = identity
    if not identity or '@' not in identity:
        logging.warning(dict(message='identity missing', usermeta=user,
                             **logmsg))
        return dict(message=_(u'access denied')), 403, None
    try:
        account = g.db.query(models.Account).join(models.Person).filter(
            models.Person.identity == identity,
            models.Account.name == account_name,
            models.Account.status == 'active').one()
    except NoResultFound:
        account = None
    except Exception as ex:
        return db_abort(str(ex), **logmsg)
    if not account:
        name = user.get('displayName') or user.get('cn')
        username = user.get(config.LDAP_PARAMS['attr_name'])
        ses = SessionAuth()
        content, status = ses.register(identity, username, name, template=None)
        if status != 200:
            return content, status, None
        content, status = ses.account_add(username, uid=content['uid'])
        if status != 201:
            return content, status, None
        account = g.db.query(models.Account).filter_by(
            id=content['id']).one()
    return {}, 200, account


def ldap_init(ldap_conn=None, ldap_mock=None):
    """Initialize LDAP server pool

    Args:
      ldap_conn (obj): an open connection (for testing)
      ldap_mock (obj): a mock (also for testing)
    """
    start = utcnow().timestamp()
    config = ServiceConfig().config

    if config.LDAP_PARAMS['servers']:
        state.ldap_serverpool = LDAPServerPool(
            None,
            pool_strategy=config.LDAP_PARAMS['pool_strategy'],
            active=config.LDAP_PARAMS['pool_active'],
            exhaust=config.LDAP_PARAMS['pool_strategy'])
        for name in config.LDAP_PARAMS['servers']:
            state.ldap_serverpool.add(LDAPServer(
                '%s://%s' % (config.LDAP_PARAMS['scheme'], name),
                port=config.LDAP_PARAMS['port'],
                allowed_referral_hosts=('*', True)))
        try:
            if config.LDAP_PARAMS['bind_dn']:
                state.ldap_conn = LDAPConnection(
                    state.ldap_serverpool, user=config.LDAP_PARAMS['bind_dn'],
                    password=config.LDAP_BIND_PASSWORD,
                    auto_bind=True, read_only=True,
                    authentication=config.LDAP_PARAMS['authentication'])
            logging.info(dict(
                action='initialize', provider='ldap',
                servers=','.join(config.LDAP_PARAMS['servers']),
                duration='%.3f' % (utcnow().timestamp() - start)))
        except Exception as ex:
            logging.error(dict(action='ldap_init', error=str(ex),
                               message='LDAP connection failure'))
    if ldap_mock:
        state.ldap_mock = ldap_mock
        state.ldap_conn = ldap_conn
