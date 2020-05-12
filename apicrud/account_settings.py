"""account_settings.py

Access class for account settings, with cache

created 13-may-2019 by richb@instantlinux.net
"""

from collections import namedtuple
from datetime import timedelta
import logging
from sqlalchemy.orm.exc import NoResultFound

from . import utils

SETTINGS = {}


class AccountSettings(object):
    def __init__(self, account_id, config, models, db_session=None, uid=None):
        """Cache per-account settings and convert to attributes"""

        def _convert(attrs):
            return namedtuple('GenericDict', attrs.keys())(**attrs)

        if account_id not in SETTINGS or (
                utils.utcnow() > SETTINGS[account_id]['expires']):
            try:
                if account_id:
                    account = db_session.query(models.Account).filter_by(
                        id=account_id).one()
                else:
                    account = db_session.query(models.Account).filter_by(
                        uid=uid).one()
                    account_id = account.id
            except NoResultFound:
                msg = 'Invalid account_id or uid'
                logging.error(dict(account_id=account_id, uid=uid,
                                   message=msg))
                return None
            record = account.settings
            try:
                category_id = db_session.query(models.Category).filter_by(
                    uid=account.uid).filter_by(
                        name='default').one().id
            except NoResultFound:
                category_id = account.settings.default_cat_id
            SETTINGS[account_id] = dict(
                expires=utils.utcnow() + timedelta(
                    seconds=config.REDIS_TTL),
                settings=dict(
                    record.as_dict(), **dict(
                        category_id=category_id,
                        sender_name=record.administrator.name,
                        sender_email=record.administrator.identity,
                        tz=record.tz.name)))
            try:
                senders = db_session.query(models.List).filter_by(
                    name=config.APPROVED_SENDERS, uid=account.uid).one()
                SETTINGS[account_id]['settings']['approved_senders'] = (
                    [member.identity for member in senders.members])
            except NoResultFound:
                SETTINGS[account_id]['settings']['approved_senders'] = []
        self.get = _convert(SETTINGS[account_id]['settings'])
        self.account_id = account_id
