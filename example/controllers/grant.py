"""grant controller

created 27-may-2019 by richb@instantlinux.net
"""

from apicrud import BasicCRUD, Grants


class GrantController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='grant')

    @staticmethod
    def create(body):
        ret = super(GrantController, GrantController).create(body)
        Grants().uncache(body.get('uid'))
        return ret

    @staticmethod
    def update(id, body):
        """If the id has a hybrid uid:grant syntax, invoke create
        instead; otherwise it's a standard update

        Args:
            id (str): Database or hybrid grant ID
            body (dict): resource fields as defined by openapi.yaml schema
        """
        Grants().uncache(body.get('uid'))
        if ':' in id:
            body['uid'] = id.split(':')[0]
            body.pop('id', None)
            return super(GrantController, GrantController).create(body)
        return super(GrantController, GrantController).update(id, body)

    @staticmethod
    def get(id):
        """Get one grant

        Args:
            id (str): Database or hybrid grant ID
        """
        return Grants().crud_get(
            super(GrantController, GrantController).get(id), id)

    @staticmethod
    def find(**kwargs):
        """Find multiple grants

        Args:
            kwargs: as defined in openapi.yaml
        """
        return Grants().find(super(GrantController, GrantController).find(
            **kwargs), **kwargs)
