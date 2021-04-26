from apicrud import BasicCRUD
import apicrud.geocode as geocode

fields = ('address', 'neighborhood', 'city', 'state', 'country')


class LocationController(BasicCRUD):

    def __init__(self):
        super().__init__(resource='location')

    @staticmethod
    def create(body):
        """invoke geocoder to store coordinates
        """
        if body.get('city') and body.get('state'):
            body['geolat'], body['geolong'], body['neighborhood'] = (
                geocode.lookup(**{item: value for item, value
                                  in body.items() if item in fields}))
        return super(LocationController, LocationController).create(body)

    @staticmethod
    def update(id, body):
        """invoke geocoder to store coordinates
        """
        if body.get('city') and body.get('state'):
            if body.get('neighborhood') and (
                    body['neighborhood'][:14] == 'A neighborhood'):
                body['neighborhood'] = None
            body['geolat'], body['geolong'], body['neighborhood'] = (
                geocode.lookup(**{item: value for item, value
                                  in body.items() if item in fields}))
        return super(LocationController, LocationController).update(id, body)

    @staticmethod
    def find(**kwargs):
        """after fetching records, convert geocoded values to
        [longitude, latitude]
        """
        results, status = super(LocationController, LocationController).find(
            **kwargs)
        for record in results['items']:
            if 'geolat' in record:
                access = 'r' if record['privacy'] == 'public' else None
                geocode.with_privacy(record, access)
        return results, status
