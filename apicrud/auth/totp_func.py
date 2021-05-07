"""totp_func

created 5-apr-2021 by richb@instantlinux.net
"""
from flask import g
from flask_babel import _
import logging
from hashlib import md5
import pyotp
from sqlalchemy.orm.exc import NoResultFound
from urllib.parse import urlparse

from .. import AccessControl, AESEncryptBin, Metrics, ServiceConfig
from ..const import Constants

# Accept previous value up to 30 seconds after OTP changes
TICKS = 1


def login(username, otp, redis_conn=None):
    """Log in with TOTP; a prior login must have succeeded and
    set up a session with the account_id and pendingotp auth, or
    with an apikey. If otp matches, this passes a sqlalchemy account
    record back for further processing by SessionAuth.login_accepted.

    Args:
      username (str): username or identity
      otp (str): 6 or 8-digit one-time password
      redis_conn (obj): connection to redis

    Returns:
      tuple: 4 items if successful; first 2 if not
        dict with error message
        http status (200 if OK)
        headers (Set-Cookie)
        account (sqlalchemy query object)
    """
    config = ServiceConfig().config
    acc = AccessControl()
    logmsg = dict(action='login_otp', username=username)
    query = g.db.query(ServiceConfig().models.Account)
    if acc.apikey_id:
        query = query.filter_by(name=username)
    else:
        query = query.filter_by(id=acc.account_id)
    try:
        account = query.one()
    except NoResultFound:
        logging.info(dict(message=u'account not found', **logmsg))
        return dict(message=_(u'access denied')), 403
    logmsg['identity'] = account.owner.identity
    if len(otp) == Constants.MFA_BACKUP_CODELEN:
        index, valid = 0, False
        codes = AESEncryptBin(config.DB_AES_SECRET).decrypt(
            account.backup_codes)
        otp_hash = md5(otp.encode()).digest()
        while index < len(codes):
            if otp_hash == codes[index:index + 16]:
                # snip the matching code
                account.backup_codes = codes[:index] + codes[index + 16:]
                g.db.commit()
                valid = True
                break
            # skip to the next 128-bit hash
            index += 16
        if not valid:
            logging.info(dict(backup_code='invalid', **logmsg))
            return dict(message=_(u'access denied')), 403
    elif not account.totp:
        msg = _(u'access denied')
        logging.warning(dict(message=msg, error='missing totp', **logmsg))
        return dict(message=msg), 403
    elif not pyotp.TOTP(account.totp_secret).verify(otp, valid_window=TICKS):
        Metrics().store('logins_fail_total')
        logging.info(dict(otp='invalid', **logmsg))
        g.db.commit()
        return dict(message=_(u'access denied')), 403
    # Block replay of same otp for next minute by setting a redis key
    result, error, status = None, 'otp replay', 403
    try:
        result = redis_conn.set(
            'totp:%s:%s' % (acc.account_id, otp), '', ex=60, nx=True)
    except Exception as ex:
        error, status = str(ex), 500
    if not result:
        msg = _(u'access denied')
        logging.warning(dict(message=msg, error=error, **logmsg))
        return dict(message=msg), status

    headers = None
    if config.LOGIN_MFA_COOKIE_LIMIT > 0:
        ses = g.session.create(
            acc.uid, [], acc=account.id, identity=account.owner.identity,
            ttl=config.LOGIN_MFA_COOKIE_LIMIT)
        hostname = urlparse(config.PUBLIC_URL).hostname
        path = '/' if acc.apikey_id else '%s/auth' % config.BASE_URL
        headers = {
            'Set-Cookie': '%s=%s; Path=%s; Max-Age=%s' % (
                config.LOGIN_MFA_COOKIE_NAME, ses.get('jti'), path,
                config.LOGIN_MFA_COOKIE_LIMIT)}
        if hostname != 'localhost':
            headers['Set-Cookie'] += (
                '; Domain=%s; HttpOnly; SameSite=Strict; Secure' % hostname)
    return {}, 200, headers, account
