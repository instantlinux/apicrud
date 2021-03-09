"""grants.py

created 27-may-2019 by richb@instantlinux.net
"""

from flask import g
from datetime import timedelta
import json
import logging

from .access import AccessControl
from .service_config import ServiceConfig
from . import utils

GRANTS = {}


class Grants(object):
    """Account usage limits

    An account's usage limits are specified here in the grants table;
    the free-service tier is defined and passed in via load_defaults().
    Records in grants table are owned by administrator-level user.
    If a record matches a user uid, the default grant name=value is
    overridden.

    Attributes:
      db_session (obj): existing db session
      ttl (int): how long to cache a grant in memory
    """

    def __init__(self, db_session=None, ttl=None):
        self.models = ServiceConfig().models
        self.session = db_session
        if not self.session:
            try:
                self.session = g.db
            except RuntimeError as ex:
                if 'Working outside of application context' not in str(ex):
                    raise
        config = ServiceConfig().config
        self.ttl = ttl or config.REDIS_TTL
        if 'defaults' not in GRANTS:
            GRANTS['defaults'] = config.DEFAULT_GRANTS

    def get(self, name, uid=None):
        """Get the cached value of a named grant, if it hasn't expired
        Note that if any grant assigned to a uid expires before
        others, the earliest expiration applies to all the uid's grants

        Args:
          name (str): name of a grant, as defined in service config
          uid (str): user ID
        Returns:
          int or str: granted limit or None if undefined
        """
        if not uid:
            uid = AccessControl().uid
        if uid not in GRANTS or utils.utcnow() > GRANTS[uid]['expires']:
            records = self.session.query(self.models.Grant).filter_by(
                uid=uid, status='active').all()
            grants = dict(expires=utils.utcnow() + timedelta(seconds=self.ttl))
            for rec in records:
                if rec.expires:
                    if rec.expires > utils.utcnow():
                        grants['expires'] = min(rec.expires, grants['expires'])
                    else:
                        continue
                grants[rec.name] = rec.value
            GRANTS[uid] = grants
        if name in GRANTS[uid] and utils.utcnow() < GRANTS[uid]['expires']:
            ret = GRANTS[uid].get(name)
        else:
            if name not in GRANTS['defaults']:
                logging.error('Grant name=%s undefined in config.yaml' % name)
            ret = GRANTS['defaults'].get(name)
        try:
            return int(ret, 0)
        except (TypeError, ValueError):
            return ret

    def crud_get(self, crud_results, id):
        """Process results from BasicCRUD.get() for grants endpoint.
        If the id is found in database, perform the standard CRUD
        get(). Otherwise, look for a hybrid id in form uid:grant and
        return the cached Grant value. Grant values are serialized as
        strings even if they are integers (decimal, octal, hex).

        Args:
            crud_results (tuple): preliminary response
            name (str): name filter, if specified
        """
        if crud_results[1] == 200 or ':' not in id:
            return crud_results
        acc = AccessControl(model=self.models.Grant)
        uid, grantname = id.split(':')
        rbac = ''.join(sorted(list(acc.rbac_permissions(owner_uid=uid))))
        if 'r' not in rbac:
            return dict('access denied'), 403
        return dict(id=id,  uid=uid, name=grantname, value=str(self.get(
            grantname, uid=uid)), rbac=rbac, status='active'), 200

    def find(self, crud_results, **kwargs):
        """Process results from BasicCRUD.find() for grants endpoint

        Args:
            crud_results (tuple): preliminary response
            name (str): name filter, if specified
        """
        filter = json.loads(kwargs.get('filter', '{}'))
        name = kwargs.get('name') or filter.get('name')
        acc = AccessControl(model=self.models.Grant)
        uid = filter.get('uid') or acc.uid
        rbac = ''.join(sorted(list(acc.rbac_permissions(owner_uid=uid))))
        result = []
        for key, val in GRANTS['defaults'].items():
            if name and key != name:
                continue
            for row in crud_results[0]['items']:
                if row['name'] == key:
                    result.append(row)
                    break
            else:
                result.append(dict(id='%s:%s' % (uid, key), uid=uid,
                                   name=key, value=str(val), rbac=rbac,
                                   status='active'))
        return dict(items=result, count=len(result)), crud_results[1]

    def uncache(self, uid):
        """Remove grants from cache, any time a user's status changes

        Args:
          uid (str): user ID
        """
        GRANTS.pop(uid, None)

    def load_defaults(self, defaults):
        """Load default values from a dict of keyword: value pairs

        Args:
          defaults (dict): new defaults
        """
        GRANTS['defaults'] = defaults
