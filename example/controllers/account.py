"""account controller

created 31-mar-2019 by richb@instantlinux.net
"""

from flask import g, request
import logging
from sqlalchemy.orm.exc import NoResultFound

from apicrud.basic_crud import BasicCRUD
import config
import i18n_textstrings as i18n
from apicrud.messaging.confirmation import Confirmation
from apicrud.session_auth import SessionAuth
from apicrud.utils import gen_id
import models
from messaging import send_contact
from apicrud import singletons


class AccountController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='account', model=models.Account,
                         config=config, models=models)

    @staticmethod
    def create(body):
        self = singletons.controller[request.url_rule.rule.split('/')[3]]
        return self._create(body)

    def _create(self, body, identity=None):
        try:
            body['settings_id'] = g.db.query(
                models.Settings).filter_by(name='global').one().id
        except NoResultFound:
            return dict(message='failed to read global settings'), 405
        body['password'] = ''
        body['password_must_change'] = True
        retval = super(AccountController, AccountController).create(body)
        if retval[1] != 201:
            return retval
        retval[0]['uid'] = body.get('uid')
        return retval

    @staticmethod
    def change_password(uid, body):
        if (not body.get('new_password') or
                body.get('new_password') != body.get('verify_password')):
            return dict(message='passwords do not match'), 405
        return SessionAuth(config=config, models=models,
                           func_send=send_contact.delay).change_password(
            uid, body.get('new_password'), body.get('reset_token'),
            old_password=body.get('old_password'))

    @staticmethod
    def get_password(uid):
        """Dummy get_password function is needed for react-admin's
        edit workflow (a get must precede put)
        """
        self = singletons.controller.get('account')
        try:
            account = g.db.query(self.model).filter_by(
                uid=uid, status='active').one()
        except NoResultFound:
            return dict(id=uid, message='account not found'), 404
        return dict(id=uid, username=account.name), 200

    @staticmethod
    def register(body):
        self = singletons.controller.get('account')
        if body.get('forgot_password'):
            return SessionAuth(
                config=config, models=models,
                func_send=send_contact.delay).forgot_password(
                    body.get('identity'), body.get('username'))
        if (not body.get('username') or not body.get('identity') or
                not body.get('name')):
            return dict(message='all fields required'), 400
        identity = body['identity'] = body.get('identity').lower()
        logmsg = dict(action='register', identity=identity,
                      username=body.get('username'))
        try:
            g.db.query(self.model).filter_by(
                name=body.get('username')).one()
            msg = 'that username is already registered'
            logging.warning(dict(message=msg, **logmsg))
            return dict(message=msg), 405
        except NoResultFound:
            pass
        uid = None
        try:
            existing = g.db.query(models.Person).filter_by(
                identity=identity).one()
            uid = existing.id
            g.db.query(models.Account).filter_by(uid=uid).one()
            msg = 'that email is already registered, use forgot-password'
            logging.warning(dict(message=msg, **logmsg))
            return dict(message=msg), 405
        except NoResultFound:
            pass
        if uid:
            try:
                cid = g.db.query(models.Contact).filter_by(
                    info=identity, type='email').one().id
            except Exception as ex:
                msg = 'registration trouble, error=%s' % str(ex)
                logging.error(dict(message=msg, **logmsg))
                return dict(message=msg), 405
        else:
            person = models.Person(
                id=gen_id(prefix='u-'), name=body['name'], identity=identity,
                status='active')
            uid = person.id
            cid = gen_id()
            g.db.add(person)
            g.db.add(models.Contact(id=cid, uid=uid, type='email',
                                    info=identity))
            g.db.commit()
            logging.info(dict(message='person added', uid=uid, **logmsg))
        Confirmation(config, models).request(cid, message=i18n.PASSWORD_RESET,
                                             func_send=send_contact.delay)
        return self._create(dict(uid=uid, name=body['username'],
                                 status='active'))
