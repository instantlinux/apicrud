"""credential.py

Credential storage

created 13-mar-2019 by richb@instantlinux.net
"""

from example import config, models
from apicrud.basic_crud import BasicCRUD


class CredentialController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='credential', config=config,
                         models=models, model=models.Credential)

    @staticmethod
    def get(id):
        """after fetching record, remove sensitive fields and convert expires
        """
        retval, status = super(CredentialController,
                               CredentialController).get(id)
        del(retval['secret'])
        del(retval['otherdata'])
        return retval, status

    @staticmethod
    def find(**kwargs):
        """after fetching record, remove sensitive fields
        """
        results, status = super(CredentialController,
                                CredentialController).find(
            **kwargs)
        for record in results['items']:
            del(record['secret'])
            del(record['otherdata'])
        return results, status
