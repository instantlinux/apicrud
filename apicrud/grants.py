"""grants.py

Grants

  An account's usage limits are specified here in the grants table;
  the free-service tier is defined and passed in via load_defaults().
  Records in grants table are owned by administrator-level user.
  If a record matches a user uid, the default grant name=value is
  overridden.

created 27-may-2019 by richb@instantlinux.net
"""

from flask import g
from datetime import timedelta

from .access import AccessControl
from . import utils

GRANTS = {}


class Grants(object):
    def __init__(self, models, db_session=None, ttl=None):
        self.ttl = ttl
        self.models = models
        try:
            self.session = db_session or g.db
        except RuntimeError as ex:
            if 'Working outside of application context' not in str(ex):
                raise

    def get(self, name, uid=None):
        """Get the cached value of a named grant, if it hasn't expired
        Note that if any grant assigned to a uid expires before
        others, the earliest expiration applies to all the uid's grants
        """
        if name not in GRANTS['defaults']:
            raise AttributeError('Unknown grant %s' % name)
        if not uid:
            uid = AccessControl().uid
        if uid not in GRANTS or utils.utcnow() > GRANTS[uid]['expires']:
            records = self.session.query(self.models.Grant).filter_by(
                uid=uid).all()
            grants = dict(expires=utils.utcnow() + timedelta(seconds=self.ttl))
            for record in records:
                grants[record.name] = record.value
                if record.expires:
                    grants['expires'] = min(record.expires, grants['expires'])
            GRANTS[uid] = grants
        if name in GRANTS[uid] and utils.utcnow() < GRANTS[uid]['expires']:
            return GRANTS[uid][name]
        return GRANTS['defaults'][name]

    def uncache(self, uid):
        GRANTS.pop(uid, None)

    def load_defaults(self, defaults):
        """Load default values from a dict of keyword: value pairs"""

        GRANTS['defaults'] = defaults
