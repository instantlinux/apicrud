"""config.py

Parameters for example API flask app

For secure installation, ALWAYS override default secrets specified here

Most immutable constants are defined in constants.py rather than here:
this file is for values that can be updated by a restart (meaning that
values copied to persistent storage such as redis/mariadb must be defined
there and NOT here)

created 31-mar-2019 by richb@instantlinux.net
"""

import binascii
import logging
import os

APPNAME = 'Example'
# Outbound messages are sent From the admin. If you want to have outbound
# messages appear From any other user, add them to a local-senders
# list of approved users. An event host's messages will otherwise show
# up with a Reply-To address to the host.
APPROVED_SENDERS = 'local-senders'

BASE_URL = '/api/v1'
if os.environ.get('DB_HOST'):
    DB_URL = ('%(dbtype)s://%(user)s:%(password)s@%(endpoint)s/%(database)s' %
              {'dbtype': os.environ.get('DB_TYPE', 'mysql+pymysql'),
               'user': os.environ.get('DB_USER', 'example'),
               'password': os.environ.get('DB_PASS', 'example'),
               'endpoint': '%s:%d' % (os.environ.get('DB_HOST'),
                                      int(os.environ.get('DB_PORT', 3306))),
               'database': os.environ.get('DB_NAME', 'example')})
else:
    DB_URL = os.environ.get('DB_URL',
                            'sqlite:////var/opt/example/example.db')

DB_AES_SECRET = os.environ.get('DB_AES_SECRET', '6VYFX61SSx63VGw5')
DB_CONNECTION_TIMEOUT = int(os.environ.get('DB_CONNECTION_TIMEOUT', 280))
DB_GEO_SUPPORT = False
DB_SCHEMA_MAXTIME = 120
DEBUG = False
DEFAULT_GRANTS = dict(
    albums=10,
    album_size=64,
    contacts=8,
    daily_email=200,
    daily_sms=100,
    lists=12,
    list_size=250,
    media_size_max=16777216,
    monthly_email=1000,
    monthly_sms=1000,
    photo_res_max=1080,
    video_duration_max=60)
HTTP_RESPONSE_CACHE_MAX_AGE = 30
JWT_ISSUER = 'example.%s' % os.environ.get('DOMAIN')
JWT_SECRET = os.environ.get('JWT_SECRET', 'PY07l0g0FSqeKsyx')
LOG_LEVEL = logging.INFO

# Adjustable parameters for login sessions
#  Time limit of sessions (measured from session start) is 2 hours in
#  production, 24 hours in dev; admin is limited to 15 minutes in prod
LOGIN_ADMIN_LIMIT = 900 if os.environ.get('EXAMPLE_ENV') == 'prod' else 86400
LOGIN_ATTEMPTS_MAX = 5
LOGIN_LOCKOUT_INTERVAL = 600
LOGIN_SESSION_LIMIT = (7200 if os.environ.get('EXAMPLE_ENV') == 'prod' else
                       86400)

PORT = os.environ.get('APP_PORT', 8080)
MAGIC_VALIDITY_HOURS_MIN = 504
MAGIC_VALIDITY_FROM_EVENT = 168
OPENAPI_FILE = 'openapi.yaml'
PUBLIC_URL = os.environ.get('PUBLIC_URL', 'http://localhost')
RBAC_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'rbac.yaml')
REDIS_AES_SECRET = os.environ.get('REDIS_AES_SECRET', '5bj27gMy6Kbb37A7P')
REDIS_HOST = os.environ.get('REDIS_HOST', 'example-redis')
REDIS_PORT = 6379
REDIS_TTL = 1200
REGISTRY_INTERVAL = 30
REGISTRY_TTL = 60
# TODO get rid of config.redis_conn, it's a unit-test hack
redis_conn = None
SECRET_KEY = binascii.unhexlify(os.environ.get(
    'FLASK_SECRET_KEY', 'e6b6935e45ea4fb381e7a0167862788d'))
SERVICE_NAME = 'main'
TOKEN_SALT = os.environ.get('TOKEN_SALT', 'lYI31A26j6f4&0#X*8&7QBNF')
TOKEN_SECRET = os.environ.get('TOKEN_SECRET', '6OoN6JYPp3t80BMf')
TOKEN_TIMEOUT = 43200

if os.environ.get('CORS_ORIGINS'):
    CORS_ORIGINS = os.environ['CORS_ORIGINS'].split(',')
elif os.environ.get('EXAMPLE_ENV') == 'prod':
    CORS_ORIGINS = [
        "https://example.$DOMAIN", "https://media.$DOMAIN"]
else:
    CORS_ORIGINS = [
        "https://dev.$DOMAIN", "https://media-dev.$DOMAIN"]
