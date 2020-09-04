"""credential.py

Credential storage

created 13-mar-2019 by richb@instantlinux.net
"""

from apicrud import BasicCRUD


class CredentialController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='credential')
