"""contact controller

created 31-mar-2019 by richb@instantlinux.net
"""

from datetime import datetime
from flask import g, request
import logging
import re
from sqlalchemy.orm.exc import NoResultFound

import config
import constants
import models
from messaging import send_contact
from apicrud.basic_crud import BasicCRUD
from apicrud.access import AccessControl
from apicrud.messaging.confirmation import Confirmation
from apicrud.grants import Grants
from apicrud import singletons


class ContactController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='contact', model=models.Contact,
                         config=config, models=models)

    @staticmethod
    def create(body):
        """after creating record, send confirmation message

        Args:
          body (dict): as defined in openapi.yaml schema
        """
        logmsg = dict(action='create', resource='contact',
                      uid=body.get('uid'))
        if body.get('type') == 'sms':
            if body['carrier'] is None:
                return dict(message='carrier required for sms'), 405
            elif not re.match(constants.REGEX_PHONE, body['info']):
                return dict(message='invalid mobile number'), 405
            body['info'] = re.sub('[- ()]', '', body['info'])
        elif body.get('type') == 'email':
            body['info'] = body['info'].strip().lower()
            if not re.match(constants.REGEX_EMAIL, body['info']):
                return dict(message='invalid email address'), 405
        elif 'type' in body and body.get('type') not in ['sms', 'email']:
            return dict(message='contact type not yet supported'), 405
        if (body.get('uid') != AccessControl().uid and
                'admin' not in AccessControl().auth):
            logging.warning(dict(message='access denied', **logmsg))
            return dict(message='access denied'), 403
        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        # Counter-measure against spammers: enforce MAX_CONTACTS_PER_USER
        max_contacts = int(Grants(models, ttl=config.REDIS_TTL).get(
            'contacts', uid=body['uid']))
        if g.db.query(self.model).filter_by(uid=body[
                'uid']).count() >= max_contacts:
            msg = 'max contacts exceeded'
            logging.warning(dict(message=msg, allowed=max_contacts, **logmsg))
            return dict(message=msg, allowed=max_contacts), 405
        if not body.get('status'):
            body['status'] = 'unconfirmed'
        retval = super(ContactController, ContactController).create(body)
        if retval[1] == 201:
            result = Confirmation(config, models).request(
                retval[0]['id'], func_send=send_contact.delay)
            retval[0].update(result[0])
        return retval

    @staticmethod
    def update(id, body):
        """special cases for contacts:

        - validate sms carrier
        - keep person identity in sync with primary contact
        - after updating record, send confirmation message

        Args:
          body (dict): as defined in openapi.yaml
        """

        logmsg = dict(action='update', id=id, info=body.get('info'))
        if body.get('type') == 'sms':
            if body['carrier'] is None:
                return dict(message='carrier required for sms'), 405
            if not re.match(constants.REGEX_PHONE, body['info']):
                return dict(message='invalid mobile number'), 405
            body['info'] = re.sub('[- ()]', '', body['info'])
        elif body.get('type') == 'email':
            body['info'] = body['info'].strip().lower()
            if not re.match(constants.REGEX_EMAIL, body['info']):
                return dict(message='invalid email address'), 405
        if 'id' in body and body['id'] != id:
            return dict(message='id is a read-only property',
                        title='Bad Request'), 405
        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        body['modified'] = datetime.utcnow()
        try:
            query = g.db.query(self.model).filter_by(id=id)
            if not AccessControl(
                    models=models, model=self.model).with_permission(
                        'u', query=query):
                return dict(message='access denied', id=id), 403
            prev_identity = query.one().info
            if body.get('status') != 'disabled':
                body['status'] = 'unconfirmed'
            query.update(body)
            try:
                # If updating primary contact, also update identity
                primary = g.db.query(models.Person).filter_by(
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
            return dict(message='conflict with existing'), 405

        retval = dict(id=id, message='updated'), 200
        result = Confirmation(config, models).request(
            retval[0]['id'], func_send=send_contact.delay)
        retval[0].update(result[0])
        return retval

    @staticmethod
    def confirmation_get(id):
        """Send a confirmation message via email (or as specified)

        Args:
          id (str): id of contact model
        """
        return Confirmation(config, models).request(
            id, func_send=send_contact.delay)

    @staticmethod
    def confirm(token):
        """Record a contact as fully confirmed

        Args:
          token (str): the token that was sent in confirmation message
        """
        # TODO parameterize this so new account gets pending role and
        # existing account gets person
        return Confirmation(config, models).confirm(token)
