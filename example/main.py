"""main.py

Flask API main entrypoint

created 31-mar-2019 by richb@instantlinux.net
"""

import connexion
from datetime import datetime
from flask import g, request
from flask_babel import Babel
import os

import controllers
import models
from apicrud import database, utils
from apicrud.access import AccessControl
from apicrud.account_settings import AccountSettings
from apicrud.service_config import ServiceConfig
from apicrud.service_registry import ServiceRegistry
from apicrud.session_manager import SessionManager

setup_db_only_once = {}
application = connexion.FlaskApp(__name__)
config = ServiceConfig(reset=True, file=os.path.join(os.path.dirname(
    os.path.abspath(__file__)), 'config.yaml'), models=models).config
utils.initialize_app(application)
babel = Babel(application.app)


@application.app.before_first_request
def setup_db(db_url=None, redis_conn=None):
    """Database setup

    Args:
      db_url (str): URL with db host, credentials and db name
      redis_conn (obj): connection to redis
    """
    db_url = db_url or config.DB_URL
    ServiceRegistry().register(controllers.resources())
    if not setup_db_only_once:
        database.initialize_db(db_url=db_url, redis_conn=redis_conn)
        setup_db_only_once['initialized'] = True


@application.app.before_request
def before_request():
    """Request-setup function - get sessions to database and auth
    """
    g.db = database.get_session()
    g.session = SessionManager()
    g.request_start_time = datetime.utcnow()


@application.app.after_request
def add_header(response):
    """All responses get a cache-control header"""
    response.cache_control.max_age = config.HTTP_RESPONSE_CACHE_MAX_AGE
    return response


@application.app.teardown_appcontext
def cleanup(resp_or_exc):
    """When a flask thread terminates, close the database session"""
    if hasattr(g, 'db'):
        g.db.remove()


@babel.localeselector
def get_locale():
    acc = AccessControl()
    if acc.auth:
        return AccountSettings(acc.account_id, db_session=g.db).locale
    return request.accept_languages.best_match(config.LANGUAGES)


if __name__ == '__main__':
    application.run(port=config.APP_PORT)
