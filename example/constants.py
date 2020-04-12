"""constants.py

Constants for API business logic

Values that can be modified by a container restart belong in config.py

created 31-mar-2019 by richb@instantlinux.net
"""

AUTH_GUEST = 'member'
AUTH_HOST = 'manager'
AUTH_INVITEE = 'invitee'
DEFAULT_AWS_REGION = 'us-east-2'
DEFAULT_BUCKET = 'apicrud-test'
DEFAULT_CAT_ID = 'x-3423ceaf'
DEFAULT_COUNTRY = u'US'
DEFAULT_LANG = u'en_US'
LOGIN_ADMIN_DEFAULTPW = ('$5$rounds=535000$YPzbABo4IekfjkMO$mWiN7'
                         '11ak8D16YNyc/x.K8FBfQBp1J3q8yrokRheSy7')
PER_PAGE_DEFAULT = 100
REDIS_TTL = 3600
REGEX_EMAIL = r'[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}'
REGEX_PHONE = r'[0-9()+ -]{5,20}'
WINDOW_TITLE = u'Example apicrud Application'
