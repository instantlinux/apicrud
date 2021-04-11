"""totp_func

created 5-apr-2021 by richb@instantlinux.net
"""
from datetime import datetime, timedelta
from flask import g
from flask_babel import _
import logging
from hashlib import md5
import pyotp
from sqlalchemy.orm.exc import NoResultFound
import time

from .. import AccessControl, AESEncryptBin, Metrics, ServiceConfig
from ..const import Constants

# Accept previous value up to 30 seconds after OTP changes
TICKS = 1


def login(username, otp, redis_conn=None):
    """Log in with TOTP; a prior login must have occured and
    set up a session with the account_id and pendingotp auth. If
    successful, this passes a sqlalchemy account record back for
    further processing by SessionAuth._login_accepted.

    Args:
      username (str): username
      otp (str): 6 or 8-digit one-type password
      redis_conn (obj): connection to redis

    Returns:
      tuple: dict with error message, http status (200 if OK), account object
    """
    config = ServiceConfig().config
    acc = AccessControl()
    try:
        account = g.db.query(ServiceConfig().models.Account).filter_by(
            id=acc.account_id).one()
    except NoResultFound:
        return dict(message=_(u'access denied')), 403
    logmsg = dict(action='login_otp', identity=account.owner.identity)
    if (account.invalid_attempts >= config.LOGIN_ATTEMPTS_MAX and
        account.last_invalid_attempt + timedelta(
            seconds=config.LOGIN_LOCKOUT_INTERVAL) > datetime.utcnow()):
        Metrics().store('logins_fail_total')
        time.sleep(5)
        msg = _(u'locked out')
        logging.warning(dict(message=msg, **logmsg))
        return dict(username=username, message=msg), 403
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
            account.invalid_attempts += 1
            account.last_invalid_attempt = datetime.utcnow()
            logging.info(dict(backup_code='invalid',
                              attempt=account.invalid_attempts, **logmsg))
            g.db.commit()
            return dict(message=_(u'access denied')), 403
    elif not account.totp_secret:
        msg = _(u'access denied')
        logging.warning(dict(message=msg, error='missing totp', **logmsg))
        return dict(message=msg), 403
    elif not pyotp.TOTP(account.totp_secret).verify(otp, valid_window=TICKS):
        account.invalid_attempts += 1
        account.last_invalid_attempt = datetime.utcnow()
        Metrics().store('logins_fail_total')
        logging.info(dict(otp='invalid', attempt=account.invalid_attempts,
                          **logmsg))
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

    return {}, 200, account
