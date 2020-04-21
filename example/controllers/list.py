from flask import g, request
import logging

from apicrud.basic_crud import BasicCRUD
from apicrud.access import AccessControl
from apicrud.grants import Grants
from apicrud import singletons
from example import config, models
from example.models import List, ListMember


class ListController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='list', model=List, config=config,
                         models=models)

    @staticmethod
    def update(id, body):
        """add multiple members
        """
        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        if body.get('members'):
            max_size = int(Grants(self.models, ttl=config.CACHE_TTL).get(
                'list_size'))
            if len(body['members']) > max_size:
                msg = 'Max list size exceeded'
                logging.warn('action=update resource=list uid=%s message=%s'
                             'allowed=%d' % (AccessControl().uid, msg,
                                             max_size))
                return dict(message=msg, allowed=max_size), 405
            self._update_many(id, 'members', body['members'])
            del(body['members'])
        return super(ListController, ListController).update(id, body)

    def _update_many(self, id, attr, related_ids):
        current = [item.id for item in getattr(
            g.db.query(self.model).filter_by(id=id).one(), attr)]
        for missing_member in set(related_ids) - set(current):
            g.db.add(ListMember(list_id=id, uid=missing_member))
        g.db.flush()
        for removed_member in set(current) - set(related_ids):
            g.db.query(ListMember).filter_by(
                list_id=id, uid=removed_member).delete()
        g.db.commit()
