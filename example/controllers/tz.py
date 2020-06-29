from apicrud.basic_crud import BasicCRUD
import config
import models


class TZController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='tz', model=models.TZname, config=config,
                         models=models)
