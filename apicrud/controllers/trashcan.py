"""trashcan.py

Trashcan

created 22-apr-2021 by richb@instantlinux.net
"""
from apicrud import Trashcan


class TrashcanController(Trashcan):
    @staticmethod
    def find(**kwargs):
        """Find deleted resources

        Args:
            kwargs: as defined in openapi.yaml
        """
        return Trashcan().find(**kwargs)

    @staticmethod
    def get(id):
        """Get one deleted resource by ID

        Args:
            id (str): Database or hybrid grant ID
        """
        return Trashcan().get(id)

    @staticmethod
    def update(id, body):
        """Update deleted resource - undelete
        """
        return Trashcan().update(id, body)

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
        return Trashcan().delete(ids)
