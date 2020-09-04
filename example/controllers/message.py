from flask import g

from apicrud import AccessControl, BasicCRUD

from models import ListMessage


class MessageController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='message')

    @staticmethod
    def create(body):
        """add to list if specified"""
        list_id = body.get('list_id')
        # TODO use many-to-many table instead, once UI is fixed
        # body.pop('list_id', None)
        body['sender_id'] = AccessControl().uid
        retval = super(MessageController, MessageController).create(body)
        if retval[1] == 201 and list_id:
            message_id = retval[0]['id']
            g.db.add(ListMessage(list_id=list_id, message_id=message_id))
            g.db.commit()
        return retval

    @staticmethod
    def update(id, body):
        """handle list_id - TODO will change when many-to-many implemented
        """
        # body.pop('list_id', None)
        return super(MessageController, MessageController).update(id, body)
