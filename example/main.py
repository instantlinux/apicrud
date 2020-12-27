"""main.py

Flask API main entrypoint

created 31-mar-2019 by richb@instantlinux.net
"""

import connexion
from datetime import datetime
from flask import abort, g, request
from flask_babel import Babel
import os

from apicrud import AccessControl, AccountSettings, RateLimit, ServiceConfig, \
    ServiceRegistry, SessionManager, database, utils

import controllers
import models

setup_db_only_once = {}
application = connexion.FlaskApp(__name__)
path = os.path.dirname(os.path.abspath(__file__))
config = ServiceConfig(
    babel_translation_directories='i18n;%s' % os.path.join(path, 'i18n'),
    reset=True, file=os.path.join(path, 'config.yaml'), models=models).config
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
    if request.method != 'OPTIONS' and RateLimit().call():
        abort(429)


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
    if acc.auth and acc.uid:
        locale = AccountSettings(acc.account_id,
                                 uid=acc.uid, db_session=g.db).locale
        if locale:
            return locale
    return request.accept_languages.best_match(config.LANGUAGES)


if __name__ == '__main__':
    application.run(port=config.APP_PORT)
