"""main.py

Flask API main entrypoint

created 31-mar-2019 by richb@instantlinux.net
"""

import connexion
from datetime import datetime
from flask import g
from flask_cors import CORS
import logging
import os

from . import config, db_schema, models
from .controllers import _init
from apicrud import database, grants, utils
from apicrud.access import AccessControl
from apicrud.session_manager import SessionManager

application = connexion.FlaskApp(__name__)


def initialize_app():
    logging.basicConfig(level=config.LOG_LEVEL,
                        format='%(asctime)s %(levelname)s %(message)s',
                        datefmt='%m-%d %H:%M:%S')
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    application.app.config.from_object(config)
    application.add_api('openapi.yaml')
    application.add_error_handler(400, utils.render_status_400)
    application.add_error_handler(connexion.ProblemException,
                                  utils.render_problem)
    CORS(application.app,
         resources={r"/api/*": {'origins': config.CORS_ORIGINS}},
         supports_credentials=True)
    AccessControl().load_rbac(os.path.join(os.path.dirname(
        os.path.abspath(__file__)), 'rbac.yaml'))
    grants.Grants(models).load_defaults(config.DEFAULT_GRANTS)
    _init.controllers()
    return application.app


initialize_app()


@application.app.before_first_request
def setup_db():
    if __name__ in ['__main__', 'uwsgi_file_main']:
        database.initialize_db(
            models, db_url=config.DB_URL, redis_host=config.REDIS_HOST,
            migrate=True, geo_support=config.DB_GEO_SUPPORT,
            connection_timeout=config.DB_CONNECTION_TIMEOUT,
            schema_update=db_schema.update,
            schema_maxtime=config.DB_SCHEMA_MAXTIME)


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
