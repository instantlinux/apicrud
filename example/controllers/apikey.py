"""apikey.py

APIkey controller

created 27-dec-2020 by richb@instantlinux.net
"""

from base64 import b64encode
from flask import g, request
from flask_babel import _
import hashlib
import logging

from apicrud import AccessControl, BasicCRUD, Grants, ServiceConfig, \
    singletons, utils
import models


class APIkeyController(BasicCRUD):
    """
    CRUD for API keys
    """
    def __init__(self):
        super().__init__(resource='apikey', model=models.APIkey)

    @staticmethod
    def create(body):
        """
        Check that user hasn't exceeded max grant for API keys, then
        generate a 41-byte string. First 8 characters (48 bits) are
        an access key ID prefix; last 32 characters (192 bits) are the
        secret key.
        """
        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        max_keys = int(Grants().get('apikeys', uid=body.get('uid')))
        logmsg = dict(action='create', resource='apikey', uid=body.get('uid'))
        if g.db.query(self.model).filter_by(uid=body[
                'uid']).count() >= max_keys:
            msg = _(u'max allowed API keys exceeded')
            logging.warning(dict(message=msg, allowed=max_keys, **logmsg))
            return dict(message=msg, allowed=max_keys), 405
        apikey = utils.gen_id(length=35, prefix='')[-32:]
        body['prefix'] = utils.gen_id(prefix='')
        body['hashvalue'] = b64encode(hashlib.sha256(
            apikey.encode()).digest()).decode('utf8')
        scopes = body.pop('scopes', None)
        ret = super(APIkeyController, APIkeyController).create(body)
        body.pop('hashvalue', None)
        if ret[1] == 201:
            ret[0]['apikey'] = body['prefix'] + '.' + apikey
            ret[0]['name'] = body['name']
            if scopes:
                ret2 = self._update_many(ret[0]['id'], 'scopes', scopes)
                if ret2[1] != 200:
                    ret[1] = ret2[1]
        return ret

    @staticmethod
    def update(id, body):
        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        if 'scopes' in body:
            retval = self._update_many(id, 'scopes', body['scopes'])
            if retval[1] == 405:
                return retval
        body.pop('scopes', None)
        body.pop('expires', None)
        return super(APIkeyController, APIkeyController).update(id, body)

    @staticmethod
    def delete(ids):
        return super(
            APIkeyController, APIkeyController).delete(ids, force=True)

    def _update_many(self, id, attr, related_ids):
        max_size = ServiceConfig().config.SCOPES_MAX
        if len(related_ids) > max_size:
            msg = 'Max list size exceeded'
            logging.warn('action=update resource=list uid=%s message=%s'
                         'allowed=%d' % (AccessControl().uid, msg,
                                         max_size))
            return dict(message=msg, allowed=max_size), 405
        current = [item.id for item in getattr(
            g.db.query(self.model).filter_by(id=id).one(), attr)]
        for missing_member in set(related_ids) - set(current):
            g.db.add(models.APIkeyScope(apikey_id=id, scope_id=missing_member))
        g.db.flush()
        for removed_member in set(current) - set(related_ids):
            g.db.query(models.APIkeyScope).filter_by(
                apikey_id=id, scope_id=removed_member).delete()
        g.db.commit()
        return dict(id=id, status='ok', items=len(related_ids)), 200
