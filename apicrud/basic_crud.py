"""basic_crud.py

Basic CRUD
  Base object for create/read/update/delete/find controller operations.


created 31-mar-2019 by richb@instantlinux.net
"""

import base64
from connexion import NoContent
from datetime import datetime, timedelta
from flask import g, request
import json
import logging
from sqlalchemy import asc, desc
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm.exc import NoResultFound

from . import constants
from .access import AccessControl
from .account_settings import AccountSettings
from . import geocode, singletons, utils


class BasicCRUD(object):

    def __init__(self, config=None, models=None, resource=None, model=None):
        self.config = config
        self.models = models
        self.resource = resource
        if self.resource not in singletons.controller:
            self.model = model
            singletons.controller[self.resource] = self

    @staticmethod
    def create(body, id_prefix='x-'):
        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        acc = AccessControl(models=self.models, model=self.model)
        logmsg = dict(action='create', account_id=acc.account_id,
                      resource=self.resource, ident=acc.identity)
        if 'id' in body:
            return dict(message='id is a read-only property',
                        title='Bad Request'), 405
        body['id'] = utils.gen_id(prefix=id_prefix)
        body['created'] = utils.utcnow()
        if body.get('expires'):
            try:
                body['expires'] = datetime.strptime(
                    body['expires'], '%Y-%m-%dT%H:%M:%S.%fZ')
            except ValueError:
                body['expires'] = datetime.strptime(
                    body['expires'], '%Y-%m-%dT%H:%M:%SZ')
        if hasattr(self.model, 'uid') and not body.get('uid'):
            body['uid'] = acc.uid
        uid = body.get('uid')
        if not acc.with_permission('c', new_uid=uid,
                                   membership=acc.primary_res,
                                   id=body.get('event_id')):
            logging.warning(dict(
                message='access denied', uid=uid, **logmsg))
            return dict(message='access denied'), 403
        logmsg['uid'] = body.get('uid')
        logging.info(dict(id=body['id'], name=body.get('name'), **logmsg))
        if not body.get('category_id') and hasattr(self.model, 'category_id'):
            if acc.account_id:
                body['category_id'] = AccountSettings(
                    acc.account_id, self.config, self.models,
                    g.db).get.category_id
            elif body.get('event_id'):
                body['category_id'] = g.db.query(self.models.Event).filter_by(
                    id=body['event_id']).one().category_id
            else:
                logging.warning(dict(message='unexpected no creds', **logmsg))
                return dict(message='access denied'), 403
        if hasattr(self.model, 'status'):
            body['status'] = body.get('status', 'active')
        try:
            record = self.model(**body)
        except (AttributeError, TypeError) as ex:
            logging.warning(dict(message=str(ex), **logmsg))
            return dict(message=str(ex)), 405
        g.db.add(record)
        try:
            g.db.commit()
        except IntegrityError as ex:
            message = 'duplicate or other conflict'
            logging.warning(dict(message=message, error=str(ex), **logmsg))
            return dict(message=message, data=str(body)), 405
        except Exception as ex:
            logging.warning(dict(message=str(ex), **logmsg))
            return dict(message=str(ex), data=str(body)), 405
        return dict(id=body['id']), 201

    @staticmethod
    def get(id):
        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        acc = AccessControl(models=self.models, model=self.model)
        try:
            query = self.db_get(id)
            record = query.one()
        except NoResultFound as ex:
            return dict(id=id, message=str(ex)), 404

        retval = record.as_dict()
        if hasattr(self.model, 'uid') and hasattr(self.model, 'owner'):
            retval['owner'] = record.owner.name
        if hasattr(self.model, 'category_id') and retval['category_id']:
            retval['category'] = record.category.name
        if 'modified' in retval and not retval['modified']:
            del(retval['modified'])
        eid = None if hasattr(self.model, 'event_id') else (
            acc.auth_ids[acc.primary_res] or [None])[0]
        retval['rbac'] = ''.join(sorted(list(
            acc.rbac_permissions(query=query, membership=acc.primary_res,
                                 id=eid) - set('c'))))
        if 'geolat' in retval:
            access = 'r' if 'r' in retval['rbac'] else None
            if retval['privacy'] == 'secret' and not access:
                return dict(message='access denied'), 403
            return geocode.with_privacy(retval, access), 200
        if 'r' in retval['rbac']:
            logging.info(dict(
                action='get', resource=self.resource, id=id,
                ident=acc.identity, duration=utils.req_duration()))
            return retval, 200
        else:
            return dict(message='access denied', id=id), 403

    @staticmethod
    def update(id, body, access='u'):
        if 'id' in body and body['id'] != id:
            return dict(message='id is a read-only property',
                        title='Bad Request'), 405
        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        body['modified'] = utils.utcnow()
        if body.get('expires'):
            try:
                body['expires'] = datetime.strptime(
                    body['expires'], '%Y-%m-%dT%H:%M:%S.%fZ')
            except ValueError:
                body['expires'] = datetime.strptime(
                    body['expires'], '%Y-%m-%dT%H:%M:%SZ')
        logmsg = dict(action='update', resource=self.resource, id=id,
                      ident=AccessControl().identity)
        try:
            query = g.db.query(self.model).filter_by(id=id)
            if not AccessControl(
                    models=self.models, model=self.model).with_permission(
                        access, query=query):
                return dict(message='access denied', id=id), 403
            current = query.one().as_dict()
            query.update(body)
            g.db.commit()
        except Exception as ex:
            logging.warning(dict(message=str(ex), **logmsg))
            return dict(message='exception %s' % str(ex)), 405

        updated = {key: body[key] for key, val in body.items()
                   if current[key] != val and key not in ('name', 'modified')}
        logging.info(dict(name=body.get('name'), duration=utils.req_duration(),
                          **logmsg, **updated))
        return dict(id=id, message='updated'), 200

    @staticmethod
    def delete(ids, force=False):
        # TODO - update auth if model could affect any session's auth
        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        logmsg = dict(action='delete', resource=self.resource,
                      account_id=AccessControl().account_id,
                      ident=AccessControl().identity)
        errors = 0
        count = 0
        for id in ids:
            try:
                query = g.db.query(self.model).filter_by(id=id)
                if not AccessControl(
                        self.models, model=self.model).with_permission(
                            'd', query=query):
                    return dict(message='access denied', id=id), 403
                if force:
                    if query.delete():
                        logging.info(dict(id=id, **logmsg))
                    else:
                        logging.info(dict(id=id, msg='query failed', **logmsg))
                        errors += 1
                else:
                    logging.info(dict(id=id, status='disabled', **logmsg))
                    query.update(dict(status='disabled'))
            except Exception as ex:
                logging.warning(dict(message=str(ex), **logmsg))
                return dict(message='exception %s' % str(ex)), 405
            count += 1
        try:
            g.db.commit()
        except Exception as ex:
            logging.warning(dict(message=str(ex), **logmsg))
            return dict(message='exception %s' % str(ex)), 405
        logging.info(dict(count=count, ids=ids, **logmsg))
        return NoContent, 404 if errors else 204

    @staticmethod
    def find(**kwargs):
        """query parameters are passed from connexion by name, in
        a dictionary that also includes user and token info

        params:
        cursor_next - pagination token to fetch subsequent records
        filter (dict) - field/value pairs to query (simple queries
            only, with string or list matching; or * for any)
        limit (int) - max records to fetch
        offset (int) - old-style pagination starting offset
        sort (str) - <field>[:{asc|desc}]
        status (str) - value is added to filter

        returns:
        dict - items (list), count(int), cursor_next (str)
        """

        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        acc = AccessControl(models=self.models, model=self.model)
        logmsg = dict(action='find', ident=acc.identity,
                      resource=self.resource)
        conditions = {item: value for item, value in kwargs.items()
                      if item in ('status')}
        if 'cursor_next' in kwargs:
            offset = int(self._fromb64(kwargs['cursor_next']).split(':')[1])
        elif 'offset' in kwargs:
            offset = int(kwargs['offset'])
        else:
            offset = 0
        sort = kwargs.get('sort',
                          'name' if hasattr(self.model, 'name') else 'id')
        if ':' in sort:
            sort, dir = sort.split(':')
            sortdir = desc if dir == 'desc' else asc
        else:
            sortdir = asc
        query = g.db.query(self.model)
        limit = int(kwargs.get('limit', constants.PER_PAGE_DEFAULT))
        try:
            filter = json.loads(kwargs.get('filter', '{}'))
        except json.decoder.JSONDecodeError as ex:
            msg = 'invalid filter string=%s' % str(ex)
            logging.error(dict(message=msg, **logmsg))
            return dict(message=msg), 405
        if 'id' in filter:
            # TODO: this seems a bit hackish, try to remember what
            # use-case this supports. The del() use-case is to
            # enable get:guest?filter{id:null,event_id=foo}
            if not filter.get('id'):
                if len(filter) == 1:
                    return dict(count=0, items=[]), 200
                else:
                    del(filter['id'])
        elif 'filter' in kwargs and not filter:
            return dict(count=0, items=[]), 200
        for key in filter.copy():
            if filter[key] == '*':
                filter.pop(key)
            elif (filter[key] and type(filter[key]) is str and '%'
                  in filter[key]):
                query = query.filter(getattr(self.model, key).like(
                    filter[key]))
                filter.pop(key)
            elif type(filter[key]) is list:
                items = filter.pop(key)
                if len(items) == 1:
                    filter[key] = items[0]
                else:
                    query = query.filter(getattr(self.model, key).in_(items))
        if hasattr(self.model, 'starts'):
            if filter.get('prev'):
                # TODO confirm whether to use utcnow()
                query = query.filter(self.model.starts < datetime.now())
            else:
                # Filter out records that start more than 12 hours ago
                query = query.filter(self.model.starts >
                                     datetime.now() - timedelta(hours=12))
            filter.pop('prev', None)
        try:
            query = query.filter_by(**filter).order_by(
                sortdir(getattr(self.model, sort)))
        except InvalidRequestError as ex:
            logging.warning(dict(message=str(ex), **logmsg))
            return dict(message='invalid filter specified'), 405
        if 'status' in conditions and conditions['status'] == 'disabled':
            query = query.filter(self.model.status == 'disabled')
        else:
            query = query.filter(self.model.status != 'disabled')
        query = acc.with_filter(query)
        try:
            results = query.slice(offset, offset + limit + 1).all()
        except Exception as ex:
            logging.error(dict(message=str(ex), **logmsg))
            return dict(message='Backend problem--probable bug'), 405
        retval = dict(items=[], count=query.count())
        count = 0
        for result in results[:limit]:
            record = result.as_dict()
            if hasattr(self.model, 'owner'):
                record['owner'] = result.owner.name
            # TODO - find a way to avoid this, causes KeyError on lazy-load
            if record.get('category_id'):
                record['category'] = result.category.name
            # TODO - takes 30ms per record for rbac: optimize or redesign
            record['rbac'] = ''.join(sorted(list(
                acc.rbac_permissions(owner_uid=record.get('uid'),
                                     membership=acc.primary_res,
                                     id=record.get('id'),
                                     privacy=record.get('privacy'))
                - set('c'))))
            retval['items'].append(record)
            count += 1
        if len(results) > limit:
            retval['cursor_next'] = self._tob64('cursor:%d' % (offset + limit))
        elif count < retval['count'] and count < limit and offset == 0:
            # TODO find a way to get query.count() to return accurate value
            retval['count'] = count
        logging.info(dict(
            offset=offset, limit=limit,
            duration=utils.req_duration(), **conditions, **logmsg))
        return retval, 200

    @staticmethod
    def _tob64(text):
        return base64.b64encode(bytes(text, 'utf8')).decode('ascii')

    @staticmethod
    def _fromb64(text):
        return base64.b64decode(bytes(text, 'utf8')).decode('ascii')

    def db_get(self, id):
        return g.db.query(self.model).filter_by(id=id)
