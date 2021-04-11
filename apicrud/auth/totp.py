"""totp

created 5-apr-2021 by richb@instantlinux.net
"""
from flask import g
from flask_babel import _
import logging
from hashlib import md5
import pyotp
import random
import string

from .. import AccessControl, AESEncryptBin, SessionAuth, database
from ..const import Constants


class AuthTOTP(SessionAuth):
    """TOTP for Session Authorization

    Functions for generating, registering and validating Time-based
    One Time Password tokens
    """
    def __init__(self):
        super().__init__()

    def generate(self):
        acc = AccessControl()
        logmsg = dict(action='totp_generate', identity=acc.identity)
        try:
            account = g.db.query(self.models.Account).filter_by(
                id=acc.account_id, status='active').one()
        except Exception as ex:
            msg = _(u'DB operational error')
            logging.error(dict(message=msg, error=str(ex), **logmsg))
            return dict(message=msg), 500
        if account.totp_secret:
            logging.info(dict(message='attempt to regenerate before revoke',
                              **logmsg))
            return dict(message=_(u'access denied')), 403
        totp = pyotp.random_base32()
        uri = pyotp.totp.TOTP(totp).provisioning_uri(
            name=account.owner.identity, issuer_name=self.config.APPNAME)
        return(dict(g.session.create(acc.uid, ['pendingtotp'],
                                     totp=totp, ttl=120, uri=uri))), 200

    def register(self, body):
        acc = AccessControl()
        logmsg = dict(action='totp_register', identity=acc.identity)
        totp_secret = g.session.get(acc.uid, body.get('nonce'), arg='totp')
        if not totp_secret:
            msg = _(u'access denied')
            logging.warning(dict(message=msg, error='totp session expired',
                                 **logmsg))
            return dict(message=msg), 403
        try:
            account = g.db.query(self.models.Account).filter_by(
                id=acc.account_id, status='active').one()
        except Exception as ex:
            msg = _(u'DB operational error')
            logging.error(dict(message=msg, error=str(ex), **logmsg))
            return dict(message=msg), 500
        if account.totp_secret:
            logging.info(dict(message='attempt to register before revoke',
                              **logmsg))
            return dict(message=_(u'access denied')), 403
        if body.get('otp_first') != pyotp.TOTP(totp_secret).now():
            msg = _(u'access denied')
            logging.warning(dict(message=msg, error='wrong otp given',
                                 **logmsg))
            return dict(message=msg), 403
        backup_codes, hashed_backup_codes = [], []
        for i in range(self.config.LOGIN_MFA_BACKUP_CODES):
            chars = string.digits + string.ascii_lowercase
            code = ''.join(random.choice(chars) for x in range(
                Constants.MFA_BACKUP_CODELEN))
            backup_codes.append(code)
            hashed_backup_codes.append(md5(code.encode()).digest())
        account.totp_secret = totp_secret
        account.backup_codes = AESEncryptBin(
            self.config.DB_AES_SECRET).encrypt(b''.join(hashed_backup_codes))
        g.db.add(account)
        try:
            g.db.commit()
        except Exception as ex:
            return database.db_abort(str(ex), rollback=True, **logmsg)
        logging.info(dict(message=_(u'registered'), **logmsg))
        # TODO - send a cookie with config.LOGIN_MFA_COOKIE_LIMIT expiration
        return dict(message=_(u'registered'), backup_codes=backup_codes), 200
