"""const.py

Constants for API library
  Values that can be modified by a container restart belong in config.py

created 31-mar-2019 by richb@instantlinux.net
"""
from flask_babel import _


class Constants:
    """Constants for apicrud methods"""
    AUTH_INVITEE = 'invitee'
    DEFAULT_AWS_REGION = 'us-east-2'
    LIB_MOD_SPATIALITE = ['/usr/lib/x86_64-linux-gnu/mod_spatialite.so',
                          '/usr/lib/mod_spatialite.so.7']
    MIME_IMAGE_TYPES = ("gif", "heic", "jpeg", "png", "svg")
    MIME_VIDEO_TYPES = ("mp4", "mpeg")
    PER_PAGE_DEFAULT = 100
    REDIS_TTL = 3600
    REGEX_EMAIL = r'[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}'
    REGEX_PHONE = r'[0-9()+ -]{5,20}'
    SERVICE_CONFIG_FILE = 'service_config.yaml'


class i18nValues:
    """These values exist only to provide msgids for generating messages.pot"""

    contact_types = dict(
        email=_(u'email'), messenger=_(u'messenger'), sms=_(u'sms'),
        voice=_(u'voice'), whatsapp=_(u'whatsapp'))
