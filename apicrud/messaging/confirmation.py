"""confirmation.py

Handle the request and confirm actions for a contact.

created 4-apr-2020 by richb@instantlinux.net
"""

from flask import g
from itsdangerous import URLSafeTimedSerializer
import logging
import random
from sqlalchemy.orm.exc import NoResultFound
import string

from ..constants import i18n


class Confirmation:

    def __init__(self, config, models):
        self.models = models
        self.token_salt = config.TOKEN_SALT
        self.token_secret = config.TOKEN_SECRET
        self.token_timeout = config.TOKEN_TIMEOUT

    def request(self, id, ttl=None, message=i18n.CONTACT_ADDED_REQUEST,
                func_send=None):
        """Generate a confirmation token valid for a given period,
        and send it to the contact identified by id
        """

        ttl = self.token_timeout if not ttl else ttl
        contact = g.db.query(self.models.Contact).filter_by(id=id).one()
        if not contact:
            return dict(id=id, message='Not Found'), 404
        serializer = URLSafeTimedSerializer(self.token_secret)
        if contact.type == u'sms':
            # For SMS, need to use a short token (less secure)
            nonce = '1'
        else:
            nonce = ''.join([random.choice(string.ascii_letters)
                             for i in range(8)])
        token = serializer.dumps('%s:%s:%s' % (
            contact.id, contact.info, nonce), salt=self.token_salt)
        g.session.create(contact.id, [], param=token, nonce=nonce, ttl=ttl)
        logging.info('action=confirmation_request id=%s info=%s' %
                     (id, contact.info))
        if func_send:
            # TODO: stop token value from leaking into celery logs
            func_send(to=id, template=message, token=token, type=contact.type)
        return dict(token=token, id=id), 200

    def confirm(self, token):
        """Confirm a contact if token is still valid
        """

        serializer = URLSafeTimedSerializer(self.token_secret)
        try:
            id, info, nonce = serializer.loads(
                token, salt=self.token_salt,
                max_age=self.token_timeout).split(':')
        except Exception as ex:
            return dict(token=token, message=str(ex)), 403
        if g.session.get(id, nonce, 'param') != token:
            logging.warning('action=confirm id=%s info=%s'
                            'message=invalid_token' % (id, info))
            return dict(id=id, message='invalid token'), 403
        # TODO need to delete session after fully confirmed
        # g.session.delete(id, nonce)
        try:
            contact = g.db.query(self.models.Contact).filter_by(id=id).one()
        except NoResultFound:
            logging.warning('action=confirm id=%s info=%s'
                            'message=Not_found' % (id, info))
            return dict(token=token, id=id, message='not found'), 404
        contact.status = u'active'
        g.db.query(self.models.Person).filter_by(id=contact.uid).update(
            dict(referrer_id=None))
        g.db.commit()

        """
        Create a login session with permissions to modify a Person/Contact
        """
        logging.info('action=confirm type=%s info=%s' %
                     (contact.type, info))
        return dict(g.session.create(
            contact.uid, ['pending'], info=info, type=contact.type,
            contact_id=id, name=contact.owner.name)), 200
