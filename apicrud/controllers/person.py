from flask import g, request
import logging

from apicrud import AccessControl, BasicCRUD, state, utils

from models import Contact


class PersonController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='person')

    @staticmethod
    def create(body):
        """create the first contact record after adding the person

        params:
          body: REST payload
        """
        body['referrer_id'] = AccessControl().uid
        retval = super(PersonController, PersonController).create(
            body, id_prefix='u-')
        if retval[1] != 201:
            return retval
        self = state.controllers[request.url_rule.rule.split('/')[3]]
        record = Contact(id=utils.gen_id(), uid=retval[0]['id'],
                         type='email', info=body['identity'],
                         status='unconfirmed')
        g.db.add(record)
        try:
            g.db.commit()
        except Exception as ex:
            logging.warn(dict(action='create', resource=self.resource,
                              message=str(ex)))
            return dict(message=str(ex), data=str(body)), 405
        return dict(id=body['id']), 201
