"""scope.py

Scopes - scoping restrictions

created 27-dec-2020 by richb@instantlinux.net
"""

from apicrud import BasicCRUD


class ScopeController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='scope')
