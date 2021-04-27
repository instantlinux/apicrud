"""trashcan.py

Trashcan

created 22-apr-2021 by richb@instantlinux.net
"""
from flask_babel import _

from apicrud import BasicCRUD, state


class TrashcanController(BasicCRUD):
    def __init__(self):
        self.resource = 'trashcan'
        if self.resource not in state.controllers:
            state.controllers[self.resource] = self

    @staticmethod
    def find(**kwargs):
        """Find deleted resources

        Args:
            kwargs: as defined in openapi.yaml
        """
        return dict(count=0, items=[]), 200

    @staticmethod
    def get(id):
        """Get one deleted resource by ID

        Args:
            id (str): Database or hybrid grant ID
        """
        return dict(message=_(u'not found')), 404

    @staticmethod
    def update(id, body):
        """Update deleted resource - undelete
        """
        return dict(message=_(u'not found')), 404

    @staticmethod
    def delete(ids):
        """Remove resources

        Args:
          ids (list of str): record IDs to be flagged for removal
        Returns:
          tuple:
            first element is a dict with the id, second element is
            response code (200 on success)
        """
        return dict(message=_(u'not found')), 404
