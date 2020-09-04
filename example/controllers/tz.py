from apicrud import BasicCRUD
import models


class TZController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='tz', model=models.Tz)
