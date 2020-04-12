"""constants.py

Constants for API library

Values that can be modified by a container restart belong in config.py

created 31-mar-2019 by richb@instantlinux.net
"""

AUTH_INVITEE = 'invitee'
DEFAULT_COUNTRY = u'US'
DEFAULT_LANG = u'en_US'
LIB_MOD_SPATIALITE = ['/usr/lib/x86_64-linux-gnu/mod_spatialite.so',
                      '/usr/lib/mod_spatialite.so.7']
PER_PAGE_DEFAULT = 100
REDIS_TTL = 3600
REGEX_EMAIL = r'[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}'
REGEX_PHONE = r'[0-9()+ -]{5,20}'
