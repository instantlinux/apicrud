"""trashcan.py

created 24-may-2021 by richb@instantlinux.net
"""

from connexion import NoContent
from flask import g, request
from flask_babel import _
import json
import logging
from sqlalchemy import asc, desc
from sqlalchemy.orm.exc import NoResultFound

from .const import Constants
from .database import db_abort
from . import AccessControl, BasicCRUD, state, utils


class Trashcan(BasicCRUD):
    """Deleted-items management

    Read/Update/Delete/find controller operations.

    This class provides permission-based, paginated access to database
    resources that have been marked inactive.
    """
    def __init__(self):
        self.models = state.models
        self.resource = 'trashcan'
        state.controllers[self.resource] = self

    @staticmethod
    def get(id):
        """Controller for GET endpoint. This method evaluates
        privacy settings against the user's permissions, looks up
        category, owner and geocode values, and fetches a single
        record.

        Args:
          id (str): composite ID of the desired resource
        Returns:
          tuple:
            first element is a dict with the object or error
            message, second element is response code (200 on success)
        """
        self = state.controllers[request.url_rule.rule.split('/')[3]]
        resource, record_id = id.split('-', maxsplit=1)
        model = getattr(self.models, resource.capitalize())
        acc = AccessControl(model=model)
        try:
            query = g.db.query(model).filter_by(id=record_id)
            record = query.one()
        except NoResultFound as ex:
            msg = _(u'not found') if 'No row was found' in str(ex) else str(ex)
            return dict(id=id, message=msg), 404

        retval = record.as_dict()
        if hasattr(model, 'uid') and hasattr(model, 'owner'):
            retval['owner'] = record.owner.name
        if 'modified' in retval and not retval['modified']:
            del(retval['modified'])
        eid = None if hasattr(model, 'event_id') else (
            acc.auth_ids[acc.primary_resource] or [None])[0]
        retval['rbac'] = ''.join(sorted(list(
            acc.rbac_permissions(query=query, membership=acc.primary_resource,
                                 id=eid) - set('c'))))
        if 'r' in retval['rbac']:
            logging.info(dict(
                action='get', resource=resource, id=id,
                ident=acc.identity, duration=utils.req_duration()))
            return retval, 200
        else:
            return dict(message=_(u'access denied'), id=id), 403

    @staticmethod
    def update(id, body):
        """Controller for PUT endpoint. This method looks for an existing
        record, evaluates user's permissions, and updates the row in
        the back-end database.

        Args:
          body (dict): fields to be updated
        Returns:
          dict:
            first element is a dict with the id, second element is
            response code (200 on success)
        """
        resource, record_id = id.split('-', maxsplit=1)
        self = state.controllers[request.url_rule.rule.split('/')[3]]
        model = getattr(self.models, resource.capitalize())
        logmsg = dict(action='update', resource=resource, id=record_id,
                      ident=AccessControl().identity)
        try:
            query = g.db.query(model).filter_by(id=record_id)
            if not AccessControl(
                    model=model).with_permission('d', query=query):
                return dict(message=_(u'access denied'), id=id), 403
            current = query.one().as_dict()
            query.update(dict(status=body.get('status')))
            g.db.commit()
        except Exception as ex:
            return db_abort(str(ex), rollback=True, **logmsg)

        updated = {key: body[key] for key, val in body.items()
                   if key in current and current[key] != val and
                   key not in ('name', 'modified')}
        logging.info(dict(name=body.get('name'), duration=utils.req_duration(),
                          **logmsg, **updated))
        return dict(id=id, message=_(u'updated')), 200

    @staticmethod
    def delete(ids):
        """Controller for DELETE endpoints. This method looks for existing
        records, evaluates user's permissions, and updates or removes
        rows in the back-end database.

        Args:
          ids (list of str): composite record IDs to be flagged for removal
        Returns:
          tuple:
            first element is a dict with the id, second element is
            response code (200 on success)
        """

        # TODO - update auth if model could affect any session's auth
        self = state.controllers[request.url_rule.rule.split('/')[3]]
        logmsg = dict(action='delete', resource='trashcan',
                      account_id=AccessControl().account_id,
                      ident=AccessControl().identity)
        errors = 0
        count = 0
        for id in ids:
            resource, record_id = id.split('-', maxsplit=1)
            if resource == 'apikey':
                model = self.models.APIkey
            else:
                model = getattr(self.models, resource.capitalize())
            try:
                query = g.db.query(model).filter_by(id=record_id)
                if not AccessControl(
                        model=model).with_permission(
                            'd', query=query):
                    return dict(message=_(u'access denied'), id=id), 403
                if query.delete():
                    logging.info(dict(id=id, **logmsg))
                else:
                    logging.info(dict(id=id, msg='query failed', **logmsg))
                    errors += 1
            except Exception as ex:
                return db_abort(str(ex), **logmsg)
            count += 1
        try:
            g.db.commit()
        except Exception as ex:
            return db_abort(str(ex), rollback=True, **logmsg)
        logging.info(dict(count=count, ids=ids, duration=utils.req_duration(),
                          **logmsg))
        return NoContent, 404 if errors else 204

    @staticmethod
    def find(**kwargs):
        """Find records which match query parameters passed from
        connexion by name, in a dictionary that also includes user
        and token info

        Due to limitation of react-admin, pagination is provided for
        both offset/limit and cursor/limit. The offset approach requires
        unfortunate hacks and is not recommended: use cursor_next.

        Args:
          cursor_next (str): pagination token to fetch subsequent records
          filter (dict): field/value pairs to query (simple queries
              only, with string or list matching; or * for any)
          limit (int): max records to fetch
          offset (int): old-style pagination starting offset
          sort (str): <field>[:{asc|desc}]
          status (str): value is added to filter
        Returns:
          dict: items (list), count(int), cursor_next (str)
        """

        self = state.controllers[request.url_rule.rule.split('/')[3]]
        acc = AccessControl()
        conditions = {item: value for item, value in kwargs.items()
                      if item in ('status')}
        logmsg = dict(action='find', ident=acc.identity, resource='trashcan',
                      **conditions)
        start_resource = '0'
        if 'cursor_next' in kwargs:
            cursor_next = self._fromb64(kwargs['cursor_next'])
            start_resource = cursor_next.split(':')[1]
            offset = int(cursor_next.split(':')[2])
        elif 'offset' in kwargs:
            offset = int(kwargs['offset'])
        else:
            offset = 0
        sort = kwargs.get('sort', 'name')
        if ':' in sort:
            sort, dir = sort.split(':')
            sortdir = desc if dir == 'desc' else asc
        else:
            sortdir = asc
        try:
            filter = json.loads(kwargs.get('filter', '{}'))
        except json.decoder.JSONDecodeError as ex:
            msg = _(u'invalid filter specified') + '=%s' % str(ex)
            logging.error(dict(message=msg, **logmsg))
            return dict(message=msg), 405
        if 'admin' not in acc.auth:
            if 'uid' in filter and filter['uid'] != acc.uid:
                msg = _(u'access denied')
                logging.info(dict(message=msg, **logmsg))
                return dict(message=msg), 403
            filter['uid'] = acc.uid
        if 'resource' in filter:
            resources = [filter.get('resource')]
            filter.pop('resource')
        else:
            if 'offset' in kwargs:
                return dict(message=_(
                    u'use cursor pagination or specify resource in filter')), \
                    405
            resources = [
                key for key in state.controllers.keys()
                if key not in ('auth', 'scope', 'settings', 'trashcan', 'tz')
                and key >= start_resource]
        if 'id' in filter and not filter.get('id'):
            # allow get:foo?filter{id:null,key=val,etc}
            del(filter['id'])
        limit = logmsg['limit'] = int(kwargs.get(
            'limit', Constants.PER_PAGE_DEFAULT))
        retval = dict(items=[], count=0)
        for resource in resources:
            if resource == 'apikey':
                model = self.models.APIkey
            else:
                model = getattr(self.models, resource.capitalize())
            query = g.db.query(model)
            acc = AccessControl(model=model)
            xfilter = filter.copy()
            for key in filter.keys():
                if key == 'uid' and resource == 'person':
                    xfilter['referrer_id'] = xfilter.pop('uid')
                    continue
                if not hasattr(model, key):
                    msg = _(u'invalid filter key')
                    logging.info(dict(message=msg, **logmsg))
                    return dict(message=msg, resource=resource), 405
                if xfilter[key] == '*':
                    xfilter.pop(key)
                elif (xfilter[key] and type(xfilter[key]) is str and '%'
                      in xfilter[key]):
                    query = query.filter(getattr(model, key).like(
                        xfilter[key]))
                    xfilter.pop(key)
                elif type(xfilter[key]) is list:
                    items = xfilter.pop(key)
                    if len(items) == 1:
                        xfilter[key] = items[0]
                    else:
                        query = query.filter(getattr(model, key).in_(items))
            try:
                query = query.filter_by(**xfilter)
                if hasattr(model, sort):
                    query = query.order_by(sortdir(getattr(model, sort)))
            except Exception as ex:
                return db_abort(str(ex), **logmsg)
            query = query.filter(model.status == 'disabled')
            query = acc.with_filter(query)
            try:
                results = query.slice(offset, offset + limit + 1).all()
            except Exception as ex:
                return db_abort(str(ex), **logmsg)
            for result in results[:limit - retval['count'] + 1]:
                if retval['count'] >= limit:
                    retval['cursor_next'] = self._tob64(
                        'cursor:%s:%d' % (resource, offset))
                    logging.info(dict(
                        offset=offset, duration=utils.req_duration(),
                        **logmsg))
                    return retval, 200
                data = result.as_dict()
                # Compose a limited amount of descriptive metadata
                record = {
                    key: data[key] for key in (
                        'created', 'modified', 'uid', 'status')
                    if hasattr(model, key)}
                record['id'] = '%s-%s' % (resource, data['id'])
                record['resource'] = resource
                record['name'] = ''
                for col in ('name', 'info', 'item', 'subject'):
                    if hasattr(model, col):
                        record['name'] = data[col]
                        break
                # TODO check for delete permission
                record['rbac'] = 'dru'
                retval['items'].append(record)
                retval['count'] += 1
                offset += 1
            if retval['items']:
                offset = 0
        logging.info(dict(
            offset=offset, duration=utils.req_duration(), **logmsg))
        return retval, 200
