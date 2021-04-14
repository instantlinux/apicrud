"""main.py

Flask API main entrypoint

created 31-mar-2019 by richb@instantlinux.net
"""

import connexion
from datetime import datetime
from flask import g, request
from flask_babel import Babel
import os

from apicrud import AccessControl, AccountSettings, Metrics, ServiceConfig, \
    database, initialize

import controllers
from messaging import send_contact
import models

application = connexion.FlaskApp(__name__)
initialize.app(application, controllers, models, os.path.dirname(
    os.path.abspath(__file__)))
config = ServiceConfig().config
babel = Babel(application.app)


def setup_db(db_url=None, redis_conn=None):
    """Database and service registry setup

    Args:
      db_url (str): URL with db host, credentials and db name
      redis_conn (obj): connection to redis
    """
    db_url = db_url or config.DB_URL
    if database.initialize_db(db_url=db_url, redis_conn=redis_conn):
        Metrics(redis_conn=redis_conn, func_send=send_contact.delay).store(
            'api_start_timestamp', value=int(datetime.now().timestamp()))


@application.app.before_request
def before_request():
    database.before_request()


@application.app.after_request
def add_header(response):
    """All responses get a cache-control header"""
    response.cache_control.max_age = config.HTTP_RESPONSE_CACHE_MAX_AGE
    if config.AUTH_SKIP_CORS:
        try:
            if request.url_rule.rule.split('/')[3] == 'auth':
                response.headers['Access-Control-Allow-Origin'] = '*'
                response.headers['Access-Control-Allow-Headers'] = (
                    'Content-Type')
        except (AttributeError, IndexError):
            pass
    Metrics().store(
        'api_request_seconds_total', value=datetime.utcnow().timestamp() -
        g.request_start_time.timestamp())
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


if __name__ in ('__main__', 'example.main'):
    setup_db(db_url=config.DB_URL)
if __name__ == '__main__':
    application.run(port=config.APP_PORT)
