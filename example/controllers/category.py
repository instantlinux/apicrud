from apicrud.basic_crud import BasicCRUD
from example import config
from example import models


class CategoryController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='category', model=models.Category,
                         config=config, models=models)
