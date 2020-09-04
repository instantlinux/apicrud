from apicrud import BasicCRUD


class SettingsController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='settings')
