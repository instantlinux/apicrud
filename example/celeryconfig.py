"""celeryconfig.py

Parameters for celery workers
Queues defined:
  messaging_prod - for message (email etc) processing
  photo_prod - for photo management

created 22-apr-2019 by richb@instantlinux.net
"""

import os

if os.environ.get('AMQ_HOST'):
    broker_url = ('%(transport)s://%(user)s:%(password)s@%(host)s:%(port)d//' %
                  {'transport': os.environ.get('AMQ_TRANSPORT', 'pyamqp'),
                   'user': os.environ.get('AMQ_USER', 'guest'),
                   'password': os.environ.get('AMQ_PASS', 'guest'),
                   'host': os.environ.get('AMQ_HOST', 'localhost'),
                   'port': int(os.environ.get('AMQ_PORT', 5672))})
else:
    broker_url = os.environ.get('AMQ_URL',
                                'pyamqp://guest:guest@10.101.2.20:5672//')
# TODO use SSL and auth
broker_use_ssl = False
enable_utc = True
result_backend = os.environ.get('CELERY_RESULT_BACKEND', 'rpc://')
task_annotations = {
   'tasks.add': {'rate_limit': os.environ.get('CELERY_RATE_LIMIT', '30/m')}
}
task_default_queue = 'sandbox'
task_routes = ([
    ('tasks.messaging.*', {'queue': 'messaging_' +
                           os.environ.get('APP_ENV', 'local')}),
    ('tasks.media.media_worker.*', {'queue': 'media_' +
                                    os.environ.get('APP_ENV', 'local')}),
],)
worker_redirect_stdouts_level = 'INFO'
