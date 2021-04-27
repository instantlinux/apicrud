"""account_settings.py

created 13-may-2019 by richb@instantlinux.net
"""

from cachetools import TTLCache
from collections import namedtuple
import logging
from sqlalchemy.orm.exc import NoResultFound

from .service_config import ServiceConfig


class AccountSettings(object):
    """Access class for account settings, with cache - converts db
    record to object attributes

    Each account is associated with an entry in the Settings model; this
    class provides access to these key-value pairs as read-only
    attributes. Because these functions are called frequently, the db
    entry is loaded into memory for a configurable expiration period
    (config.REDIS_TTL).

    Args:
      account_id (str): ID in database of a user's account
      db_session (obj): a session connected to database
      uid (str): User ID
    """
    _singleton = None
    _cache = None
    _admin_id = None

    def __init__(self, account_id, db_session=None, uid=None):
        """Cache per-account settings and convert to attributes"""

        def _convert(attrs):
            return namedtuple('GenericDict', attrs.keys())(**attrs)

        config = ServiceConfig().config
        models = self.models = ServiceConfig().models
        if account_id not in self._cache:
            try:
                if account_id:
                    account = db_session.query(models.Account).filter_by(
                        id=account_id).one()
                    uid = account.uid
                else:
                    account = db_session.query(models.Account).filter_by(
                        uid=uid).one()
                    account_id = account.id
                record = account.settings
            except NoResultFound:
                if self._admin_id:
                    # Already cached
                    return self.__init__(self._admin_id, db_session=db_session)
                try:
                    record = db_session.query(models.Settings).filter_by(
                        name='global').one()
                    account = db_session.query(models.Account).filter_by(
                        uid=record.administrator_id).one()
                except Exception as ex:
                    logging.error(dict(action='AccountSettings',
                                       error=str(ex)))
                    return None
                uid = record.administrator_id
                self._admin_id = account_id = account.id
            try:
                category_id = db_session.query(models.Category).filter_by(
                    uid=uid).filter_by(name='default').one().id
            except NoResultFound:
                category_id = record.default_cat_id
            self._cache[account_id] = dict(
                uid=uid,
                settings=dict(
                    record.as_dict(), **dict(
                        category_id=category_id,
                        sender_name=record.administrator.name,
                        sender_email=record.administrator.identity,
                        tz=record.tz.name)))
            try:
                senders = db_session.query(models.List).filter_by(
                    name=config.APPROVED_SENDERS,
                    uid=record.administrator_id).one()
                self._cache[account_id]['settings']['approved_senders'] = (
                    [member.identity for member in senders.members])
            except NoResultFound:
                self._cache[account_id]['settings']['approved_senders'] = []
        self.get = _convert(self._cache[account_id]['settings'])
        self.account_id = account_id
        self.uid = self._cache[account_id]['uid']
        self.db_session = db_session
        self.default_locale = config.BABEL_DEFAULT_LOCALE

    def __new__(cls,  account_id, db_session=None, uid=None):
        if cls._singleton is None:
            cls._singleton = super(AccountSettings, cls).__new__(cls)
            config = ServiceConfig().config
            cls._cache = TTLCache(maxsize=config.CACHE_SIZE,
                                  ttl=config.REDIS_TTL)
        return cls._singleton

    def uncache(self):
        """Clear the cached settings for account_id"""
        self._cache.pop(self.account_id, None)

    @property
    def locale(self):
        """Returns the language for the uid if specified in the
        user's profile
        """
        try:
            return self.db_session.query(self.models.Profile).filter(
                self.models.Profile.uid == self.uid,
                self.models.Profile.item == 'lang').one().value
        except NoResultFound:
            return None
