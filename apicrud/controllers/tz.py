from apicrud import BasicCRUD


class TZController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='tz')
