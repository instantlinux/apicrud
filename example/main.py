"""main.py

Flask API main entrypoint

created 31-mar-2019 by richb@instantlinux.net
"""

import connexion
from datetime import datetime
from flask import g

from . import config, db_schema, models
from .controllers import _init
from apicrud import database, utils
from apicrud.session_manager import SessionManager

setup_db_only_once = {}
application = connexion.FlaskApp(__name__)
utils.initialize_app(application, config, models)
_init.controllers()


@application.app.before_first_request
def setup_db(db_url=config.DB_URL, redis_conn=None):
    if not setup_db_only_once:
        database.initialize_db(
            models, db_url=db_url, redis_host=config.REDIS_HOST,
            redis_conn=redis_conn,
            migrate=True, geo_support=config.DB_GEO_SUPPORT,
            connection_timeout=config.DB_CONNECTION_TIMEOUT,
            schema_update=db_schema.update,
            schema_maxtime=config.DB_SCHEMA_MAXTIME)
        setup_db_only_once['initialized'] = True


@application.app.before_request
def before_request():
    g.db = database.get_session()
    g.session = SessionManager(config, redis_conn=config.redis_conn)
    g.request_start_time = datetime.utcnow()


@application.app.after_request
def add_header(response):
    response.cache_control.max_age = config.CACHE_API
    return response


@application.app.teardown_appcontext
def cleanup(resp_or_exc):
    g.db.remove()


if __name__ == '__main__':
    application.run(port=config.PORT)
