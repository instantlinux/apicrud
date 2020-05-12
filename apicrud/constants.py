"""constants.py

Constants for API library

Values that can be modified by a container restart belong in config.py

created 31-mar-2019 by richb@instantlinux.net
"""

AUTH_INVITEE = 'invitee'
DEFAULT_AWS_REGION = 'us-east-2'
LIB_MOD_SPATIALITE = ['/usr/lib/x86_64-linux-gnu/mod_spatialite.so',
                      '/usr/lib/mod_spatialite.so.7']
MIME_IMAGE_TYPES = ("gif", "heic", "jpeg", "png", "svg")
MIME_VIDEO_TYPES = ("mp4", "mpeg")
PER_PAGE_DEFAULT = 100
REDIS_TTL = 3600


class i18n:
    # These are keys in a user-provided dict; see the
    # example/i18n_textstrings.py for how to assign string
    # templates for messaging
    # TODO - update this doc when messaging code is moved
    # into this library
    CONTACT_ADDED_REQUEST = 'contact_add'
    PASSWORD_RESET = 'password_reset'
