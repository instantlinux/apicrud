"""basic_crud.py

created 31-mar-2019 by richb@instantlinux.net
"""

import base64
from connexion import NoContent
from datetime import datetime, timedelta
from flask import g, request
from flask_babel import _
import json
import logging
import re
from sqlalchemy import asc, desc
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm.exc import NoResultFound

from .access import AccessControl
from .account_settings import AccountSettings
from .const import Constants
from .grants import Grants
from .service_config import ServiceConfig
from . import geocode, singletons, utils


class BasicCRUD(object):
    """Controller base class

    Create/Read/Update/Delete/find controller operations.

    This class provides permission-based, paginated access to database
    models behind your application's endpoints. Most endpoints need no
    boilerplate code, and can inherit these functions directly. Some
    endpoints only need a few lines of code before or after inheriting
    these functions. You can always write your own custom function for
    special-case endpoints.

    Args:
      resource (str): a resource name (endpoint prefix)
      model (obj): the model corresponding to the resource
    """

    def __init__(self, resource=None, model=None):
        self.models = ServiceConfig().models
        self.resource = resource
        if self.resource not in singletons.controller:
            if model:
                self.model = model
            else:
                self.model = getattr(self.models, resource.capitalize())
            singletons.controller[self.resource] = self

    @staticmethod
    def create(body, id_prefix='x-', limit_related={}):
        """Controller for POST endpoints. This method assigns a new
        object ID, sets the _created_ timestamp, evaluates user's
        permissions, adds a default category_id if the model has
        this attribute, and inserts a row to the back-end database.

        Args:
          body (dict): resource fields as defined by openapi.yaml schema
          id_prefix (str): generated objects will be assigned a random 10-
            to 16-character ID; you can set a unique prefix if desired
          limit_related (dict): limits on number of related records,
            keyed by relationship name
        Returns:
          tuple:
            first element is a dict with the id, second element is
            response code (201 on success)
        """

        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        # TODO reject extraneous keys beyond those in the openapi path spec
        if self.resource == 'contact':
            retval = self._create_contact(body)
            if retval[1] != 201:
                return retval
        acc = AccessControl(model=self.model)
        logmsg = dict(action='create', account_id=acc.account_id,
                      resource=self.resource, ident=acc.identity)
        if 'id' in body:
            return dict(message='id is a read-only property',
                        title='Bad Request'), 405
        body['id'] = id = utils.gen_id(prefix=id_prefix)
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
        uid = logmsg['uid'] = body.get('uid')
        if not acc.with_permission('c', new_uid=uid,
                                   membership=acc.primary_res,
                                   id=body.get('event_id')):
            logging.warning(dict(message='access denied', **logmsg))
            return dict(message=_(u'access denied')), 403
        ret_info = {}
        logging.info(dict(id=id, name=body.get('name'), **logmsg))
        if not body.get('category_id') and hasattr(self.model, 'category_id'):
            if acc.account_id:
                body['category_id'] = AccountSettings(
                    acc.account_id, g.db).get.category_id
            elif body.get('event_id'):
                body['category_id'] = g.db.query(self.models.Event).filter_by(
                    id=body['event_id']).one().category_id
            else:
                logging.warning(dict(message='unexpected no creds', **logmsg))
                return dict(message=_(u'access denied')), 403
        if hasattr(self.model, 'status'):
            body['status'] = body.get('status', 'active')

        grant = (self.resource if self.resource.endswith('s')
                 else self.resource + 's')
        limit = Grants().get(grant, uid=uid)
        if grant in ServiceConfig().config.DEFAULT_GRANTS and g.db.query(
                self.model).filter_by(uid=uid).count() >= limit:
            msg = _('user limit exceeded')
            logging.info(dict(message=msg, allowed=limit, **logmsg))
            return dict(message=msg, allowed=limit), 405
        related_items = None
        if hasattr(self.model, '__rest_related__'):
            related_items = {
                item: body[item] for item in self.model.__rest_related__
                if item in body}
            for related in self.model.__rest_related__:
                if (related in body and related in limit_related and
                        len(body[related]) > limit_related[related]):
                    logging.warning(dict(message='limit exceeded',
                                         field=related, **logmsg))
                    return dict(message=_(u'limit exceeded')), 405
                body.pop(related, None)
        if self.resource == 'apikey':
            body['prefix'], secret, body['hashvalue'] = acc.apikey_create()
            ret_info = dict(apikey=body['prefix'] + '.' + secret,
                            name=body['name'])
        try:
            record = self.model(**body)
        except (AttributeError, TypeError) as ex:
            logging.warning(dict(message=str(ex), **logmsg))
            return dict(message=str(ex)), 405
        g.db.add(record)
        try:
            if related_items:
                g.db.commit()
                for related, records in related_items.items():
                    self._update_related(id, related, records)
            g.db.commit()
        except IntegrityError as ex:
            message = 'duplicate or other conflict'
            logging.warning(dict(message=message, error=str(ex), **logmsg))
            return dict(message=message, data=str(body)), 405
        except Exception as ex:
            logging.warning(dict(message=str(ex), **logmsg))
            return dict(message=str(ex), data=str(body)), 405
        return dict(id=id, **ret_info), 201

    @staticmethod
    def get(id):
        """Controller for GET endpoints. This method evaluates
        privacy settings against the user's permissions, looks up
        category, owner and geocode values, and fetches the object
        from back-end database.

        Args:
          id (str): ID of the desired resource
        Returns:
          tuple:
            first element is a dict with the object or error
            message, second element is response code (200 on success)
        """

        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        acc = AccessControl(model=self.model)
        try:
            query = self.db_get(id)
            record = query.one()
        except NoResultFound as ex:
            msg = _(u'not found') if 'No row was found' in str(ex) else str(ex)
            return dict(id=id, message=msg), 404

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
                return dict(message=_(u'access denied')), 403
            return geocode.with_privacy(retval, access), 200
        if 'r' in retval['rbac']:
            logging.info(dict(
                action='get', resource=self.resource, id=id,
                ident=acc.identity, duration=utils.req_duration()))
            return retval, 200
        else:
            return dict(message=_(u'access denied'), id=id), 403

    @staticmethod
    def update(id, body, access='u', limit_related={}):
        """Controller for PUT endpoints. This method looks for an existing
        record, evaluates user's permissions, and updates the row in
        the back-end database.

        Args:
          body (dict): fields to be updated
          access (str): access-level required for RBAC evaluation
          limit_related (dict): limits on number of related records,
            indexed by relationship name
        Returns:
          dict:
            first element is a dict with the id, second element is
            response code (200 on success)
        """
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
        if hasattr(self.model, '__rest_related__'):
            for related in self.model.__rest_related__:
                if related in body:
                    ret = self._update_related(
                        id, related, body.pop(related, None),
                        limit=(limit_related[related]
                               if related in limit_related else None))
                    if ret[1] != 200:
                        return ret
        logmsg = dict(action='update', resource=self.resource, id=id,
                      ident=AccessControl().identity)
        try:
            query = g.db.query(self.model).filter_by(id=id)
            if not AccessControl(
                    model=self.model).with_permission(
                        access, query=query):
                return dict(message=_(u'access denied'), id=id), 403
            current = query.one().as_dict()
            query.update(body)
            g.db.commit()
        except IntegrityError as ex:
            message = _(u'duplicate or other conflict')
            logging.warning(dict(message=message, error=str(ex), **logmsg))
            return dict(message=message, data=str(ex)), 405
        except Exception as ex:
            logging.warning(dict(message=str(ex), **logmsg))
            return dict(message='exception %s' % str(ex)), 405

        updated = {key: body[key] for key, val in body.items()
                   if key in current and current[key] != val and
                   key not in ('name', 'modified')}
        logging.info(dict(name=body.get('name'), duration=utils.req_duration(),
                          **logmsg, **updated))
        return dict(id=id, message=_(u'updated')), 200

    @staticmethod
    def delete(ids, force=False):
        """Controller for DELETE endpoints. This method looks for existing
        records, evaluates user's permissions, and updates or removes
        rows in the back-end database.

        Args:
          ids (list of str): record IDs to be flagged for removal
          force (bool): flag for removal if false; remove data if true
        Returns:
          tuple:
            first element is a dict with the id, second element is
            response code (200 on success)
        """

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
                        model=self.model).with_permission(
                            'd', query=query):
                    return dict(message=_(u'access denied'), id=id), 403
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
        """Find records which match query parameters passed from
        connexion by name, in a dictionary that also includes user
        and token info

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

        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        acc = AccessControl(model=self.model)
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
        limit = int(kwargs.get('limit', Constants.PER_PAGE_DEFAULT))
        try:
            filter = json.loads(kwargs.get('filter', '{}'))
        except json.decoder.JSONDecodeError as ex:
            msg = _(u'invalid filter specified') + '=%s' % str(ex)
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
                query = query.filter(self.model.starts < utils.utcnow())
            else:
                # Filter out records that start more than 12 hours ago
                query = query.filter(self.model.starts >
                                     utils.utcnow() - timedelta(hours=12))
            filter.pop('prev', None)
        try:
            query = query.filter_by(**filter).order_by(
                sortdir(getattr(self.model, sort)))
        except InvalidRequestError as ex:
            logging.warning(dict(message=str(ex), **logmsg))
            return dict(message=_(u'invalid filter specified')), 405
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

    def _create_contact(self, body):
        """Perform pre-checks against fields for contact resource
        prior to rest of contact-create

        Args:
            body (dict): as defined in openapi.yaml schema
        """
        logmsg = dict(action='create', resource='contact',
                      uid=body.get('uid'))
        if body.get('type') == 'sms':
            if body['carrier'] is None:
                return dict(message=_(u'carrier required for sms')), 405
            elif not re.match(Constants.REGEX_PHONE, body['info']):
                return dict(message=_(u'invalid mobile number')), 405
            body['info'] = re.sub('[- ()]', '', body['info'])
        elif body.get('type') == 'email':
            body['info'] = utils.identity_normalize(body['info'].strip())
            if not re.match(Constants.REGEX_EMAIL, body['info']):
                return dict(message=_(u'invalid email address')), 405
        elif 'type' in body and body.get('type') not in ['sms', 'email']:
            return dict(message='contact type not yet supported'), 405
        if (body.get('uid') != AccessControl().uid and
                'admin' not in AccessControl().auth):
            logging.warning(dict(message=_(u'access denied'), **logmsg))
            return dict(message=_(u'access denied')), 403
        if not body.get('status'):
            body['status'] = 'unconfirmed'
        return dict(status='ok'), 201

    @staticmethod
    def update_contact(id, body):
        """This is a special-case function for the contact-update resource

        - validate sms carrier
        - keep person identity in sync with primary contact

        Args:
          id (str): resource ID
          body (dict): as defined in openapi.yaml
        """

        logmsg = dict(action='update', id=id, info=body.get('info'))
        if body.get('type') == 'sms':
            if body['carrier'] is None:
                return dict(message=_(u'carrier required for sms')), 405
            if not re.match(Constants.REGEX_PHONE, body['info']):
                return dict(message=_(u'invalid mobile number')), 405
            body['info'] = re.sub('[- ()]', '', body['info'])
        elif body.get('type') == 'email':
            body['info'] = utils.identity_normalize(body['info'].strip())
            if not re.match(Constants.REGEX_EMAIL, body['info']):
                return dict(message=_(u'invalid email address')), 405
        if 'id' in body and body['id'] != id:
            return dict(message='id is a read-only property',
                        title='Bad Request'), 405
        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        body['modified'] = utils.utcnow()
        try:
            query = g.db.query(self.model).filter_by(id=id)
            if not AccessControl(model=self.model).with_permission(
                    'u', query=query):
                return dict(message=_(u'access denied'), id=id), 403
            prev_identity = query.one().info
            if body.get('status') != 'disabled':
                body['status'] = 'unconfirmed'
            query.update(body)
            try:
                # If updating primary contact, also update identity
                primary = g.db.query(self.models.Person).filter_by(
                    identity=prev_identity).one()
                logging.info(dict(
                    resource='person', previous=prev_identity, **logmsg))
                primary.identity = body.get('info')
            except NoResultFound:
                pass
            g.db.commit()
            logging.info(dict(resource=self.resource, **logmsg))
        except Exception as ex:
            logging.warning(dict(message=str(ex), **logmsg))
            g.db.rollback()
            return dict(message=_(u'conflict with existing')), 405

        return dict(id=id, message=_(u'updated')), 200

    def _update_related(self, id, attr, related_ids, limit=None):
        """Update the list of records in the many-to-many association
        model for one column in the record. Adds and/or removes entries
        from the association table to make the list match related_ids.

        Args:
          id (str): ID of record in current model
          attr (str): relationship attribute name
          related_ids (list): list of existing records in related table
          limit (int): maximum number of allowed records

        Returns: tuple
          flask-compatible status dict, http return status
        """
        if limit and len(related_ids) > limit:
            msg = 'Limit exceeded'
            logging.warn(dict(
                action='update', resource=self.resource, allowed=limit,
                field=attr, uid=AccessControl().uid, message=msg))
            return dict(message=msg, allowed=limit), 405
        if attr == 'members':
            model = getattr(self.models, 'Person')
        else:
            model = getattr(self.models, attr.capitalize().strip('s'))
        query = g.db.query(self.model).filter_by(id=id).one()
        current = [item.id for item in getattr(query, attr)]
        for missing_member in set(related_ids) - set(current):
            getattr(query, attr).append(g.db.query(model).filter_by(
                id=missing_member).one())
        g.db.flush()
        for removed_member in set(current) - set(related_ids):
            getattr(query, attr).remove(g.db.query(model).filter_by(
                id=removed_member).one())
        g.db.commit()
        return dict(id=id, status='ok', items=len(related_ids)), 200

    @staticmethod
    def _tob64(text):
        return base64.b64encode(bytes(text, 'utf8')).decode('ascii')

    @staticmethod
    def _fromb64(text):
        return base64.b64decode(bytes(text, 'utf8')).decode('ascii')

    def db_get(self, id):
        """Activate a SQLalchemy query object for the specified ID in
        the current model

        Args:
          id (str): object ID
        Returns:
          obj: query object
        """
        return g.db.query(self.model).filter_by(id=id)
