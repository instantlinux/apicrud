from apicrud.basic_crud import BasicCRUD
import models


class CategoryController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='category', model=models.Category,
                         models=models)
