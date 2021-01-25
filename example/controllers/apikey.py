"""apikey.py

APIkey controller

created 27-dec-2020 by richb@instantlinux.net
"""

from apicrud import BasicCRUD, ServiceConfig
import models


class APIkeyController(BasicCRUD):
    """
    CRUD for API keys
    """
    def __init__(self):
        super().__init__(resource='apikey', model=models.APIkey)

    @staticmethod
    def create(body):
        return super(APIkeyController, APIkeyController).create(
            body, limit_related=dict(
                scopes=ServiceConfig().config.SCOPES_MAX))

    @staticmethod
    def update(id, body):
        body.pop('expires', None)
        return super(APIkeyController, APIkeyController).update(
            id, body, limit_related=dict(
                scopes=ServiceConfig().config.SCOPES_MAX))

    @staticmethod
    def delete(ids):
        """Undelete is disabled"""
        return super(
            APIkeyController, APIkeyController).delete(ids, force=True)
