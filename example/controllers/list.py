from flask import g, request
import logging

from apicrud import AccessControl, BasicCRUD, Grants, singletons

from models import ListMember


class ListController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='list')

    @staticmethod
    def create(body):
        """create and then add members if included in request
        """
        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        members = body.pop('members', None)
        retval = super(ListController, ListController).create(body)
        if members and retval[1] == 201:
            return self._update_many(retval[0]['id'], 'members', members)
        return retval

    @staticmethod
    def update(id, body):
        """add multiple members
        """
        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        if body.get('members'):
            retval = self._update_many(id, 'members', body['members'])
            if retval[1] == 405:
                return retval
        body.pop('members', None)
        return super(ListController, ListController).update(id, body)

    def _update_many(self, id, attr, related_ids):
        max_size = int(Grants().get('list_size'))
        if len(related_ids) > max_size:
            msg = 'Max list size exceeded'
            logging.warn('action=update resource=list uid=%s message=%s'
                         'allowed=%d' % (AccessControl().uid, msg,
                                         max_size))
            return dict(message=msg, allowed=max_size), 405
        current = [item.id for item in getattr(
            g.db.query(self.model).filter_by(id=id).one(), attr)]
        for missing_member in set(related_ids) - set(current):
            g.db.add(ListMember(list_id=id, uid=missing_member))
        g.db.flush()
        for removed_member in set(current) - set(related_ids):
            g.db.query(ListMember).filter_by(
                list_id=id, uid=removed_member).delete()
        g.db.commit()
        return dict(id=id, status='ok', items=len(related_ids)), 200
