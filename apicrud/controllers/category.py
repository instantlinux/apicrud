from apicrud import BasicCRUD


class CategoryController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='category')
