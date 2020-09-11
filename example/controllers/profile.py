"""profile controller

created 27-may-2019 by richb@instantlinux.net
"""

from apicrud import BasicCRUD


class ProfileController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='profile')
