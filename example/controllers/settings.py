from apicrud.basic_crud import BasicCRUD
from example import config, models


class SettingsController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='settings', model=models.Settings,
                         config=config, models=models)
