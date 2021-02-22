"""geocode.py

Geocode functions

created 7-mar-2020 by richb@instantlinux.net
"""

# from geoalchemy2 import functions
import geocoder
import logging

from .access import AccessControl
from .metrics import Metrics


def lookup(address=None, neighborhood=None, city=None, state=None,
           country=None):
    """Geo-code an address and get its neighbhorhood name
    To make this compatible with any database, coordinates are stored
    as integers with 7-digit decimal precision to fit in 32 bits

    Args:
      address (str): street address
      neighborhood (str): neighborhood name
      city (str): city
      state (str): state
      country (str): 2-letter country abbreviation
    Returns:
      tuple: lat, long, neighborhood
    """

    location = '%s,%s,%s' % (city, state, country)
    if address or neighborhood:
        location = '%s,%s' % (address or neighborhood, location)
    try:
        geo = geocoder.mapquest(location)
    except Exception as ex:
        if 'Provide API Key' in str(ex):
            logging.error('geocode: no MapQuest key set')
        else:
            logging.warning('action=geo_lookup error=%s' % str(ex))
        return (None, None, '')

    # POINT column type only supported in PostgreSQL / sqlite
    # geo = 'POINT(%f %f)' % (geo.lng, geo.lat)
    geolat = int(geo.lat * 1.0e7)
    geolong = int(geo.lng * 1.0e7)
    if address and not neighborhood:
        # TODO neighborhood-lookup support
        neighborhood = 'A neighborhood%s' % (' in %s' % city if city else '')
    logging.info('geocode: lat=%f long=%f neighborhood="%s"' % (
        geo.lat, geo.lng, neighborhood))
    Metrics().store('geo_lookup_total')
    return (geolat, geolong, neighborhood)


def with_privacy(record, access):
    """Convert a database record's geo values for API response
    Input is a value from model as_dict.  Evaluates uid,
    geolat, geolong, address fields. If the record is private,
    last 4 digits are rounded off.

    Args:
      record (dict): dict of key/value pairs from database
      access (str): access required for full location disclosure
    Returns:
      dict: record geolat/geolong values removed and geo tuple added
    """

    if access == 'r' or record['uid'] == AccessControl().uid:
        if record.get('geolat') and record.get('geolong'):
            record['geo'] = [record['geolong'] / 1.0e7,
                             record['geolat'] / 1.0e7]
    else:
        if record.get('geolat') and record.get('geolong'):
            record['geo'] = [round(record['geolong'] / 1.0e7, 4),
                             round(record['geolat'] / 1.0e7, 4)]
            if 'address' in record:
                record['address'] = ''
    record.pop('geolong', None)
    record.pop('geolat', None)
    return record
