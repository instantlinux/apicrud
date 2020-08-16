"""grant controller

created 27-may-2019 by richb@instantlinux.net
"""

from apicrud.basic_crud import BasicCRUD
from apicrud.access import AccessControl
from apicrud.grants import Grants
from apicrud.service_config import ServiceConfig


class GrantController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='grant')

    @staticmethod
    def create(body):
        Grants().uncache(body.get('uid'))
        return super(GrantController, GrantController).create(body)

    @staticmethod
    def update(id, body):
        Grants().uncache(body.get('uid'))
        return super(GrantController, GrantController).update(id, body)

    @staticmethod
    def find(**kwargs):
        retval = super(GrantController, GrantController).find(**kwargs)
        config = ServiceConfig().config
        if 'name' in kwargs and retval[0]['count'] == 0:
            return dict(count=1, items=[dict(
                name=kwargs.get('name'),
                value=Grants().get(kwargs.get('name')),
                uid=AccessControl().uid)]), 200
        response = config.DEFAULT_GRANTS.copy()
        for item in retval[0]['items']:
            response[item['name']] = item['value']
        return dict(
            items=[dict(name=k, value=v) for k, v in response.items()],
            count=len(config.DEFAULT_GRANTS)), retval[1]
