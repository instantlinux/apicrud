"""constants.py

Constants for API business logic

Values that can be modified by a container restart belong in config.yaml

created 31-mar-2019 by richb@instantlinux.net
"""

AUTH_GUEST = 'member'
AUTH_HOST = 'manager'
AUTH_INVITEE = 'invitee'

# These values are defaults for the settings records on new accounts
DEFAULT_AWS_REGION = 'us-east-2'
DEFAULT_BUCKET = 'apicrud-test'
DEFAULT_COUNTRY = u'US'
DEFAULT_LANG = u'en_US'
DEFAULT_WINDOW_TITLE = u'Example apicrud Application'

REGEX_EMAIL = r'[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}'
REGEX_PHONE = r'[0-9()+ -]{5,20}'
