"""contact controller

created 31-mar-2019 by richb@instantlinux.net
"""

from apicrud.basic_crud import BasicCRUD
from apicrud.messaging.confirmation import Confirmation

from messaging import send_contact


class ContactController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='contact')

    @staticmethod
    def create(body):
        """after creating record, send confirmation message

        Args:
          body (dict): as defined in openapi.yaml schema
        """
        retval = super(ContactController, ContactController).create(body)
        if retval[1] == 201:
            result = Confirmation().request(
                retval[0]['id'], func_send=send_contact.delay)
            retval[0].update(result[0])
        return retval

    @staticmethod
    def update(id, body):
        """contact update - uses special-case function

        Args:
          id (str): resource ID
          body (dict): as defined in openapi.yaml
        """
        retval = super(ContactController, ContactController).update_contact(
            id, body)
        if retval[1] == 200:
            result = Confirmation().request(id, func_send=send_contact.delay)
            retval[0].update(result[0])
        return retval

    @staticmethod
    def confirmation_get(id):
        """Send a confirmation message via email (or as specified)

        Args:
          id (str): id of contact model
        """
        return Confirmation().request(id, func_send=send_contact.delay)

    @staticmethod
    def confirm(token):
        """Record a contact as fully confirmed

        Args:
          token (str): the token that was sent in confirmation message
        """
        # TODO parameterize this so new account gets pending role and
        # existing account gets person
        return Confirmation().confirm(token)
