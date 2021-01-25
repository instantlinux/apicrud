from apicrud import BasicCRUD, Grants


class ListController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='list')

    @staticmethod
    def create(body):
        return super(ListController, ListController).create(
            body, limit_related=dict(
                members=int(Grants().get('list_size'))))

    @staticmethod
    def update(id, body):
        return super(ListController, ListController).update(
            id, body, limit_related=dict(
                members=int(Grants().get('list_size'))))
