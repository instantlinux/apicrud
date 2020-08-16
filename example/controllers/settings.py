from apicrud.basic_crud import BasicCRUD
import models


class SettingsController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='settings', model=models.Settings,
                         models=models)
