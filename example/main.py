"""main.py

Flask API main entrypoint

created 31-mar-2019 by richb@instantlinux.net
"""
import connexion
from flask import g
from flask_babel import Babel
import os

from apicrud import ServiceConfig, initialize

import controllers
from messaging import send_contact
import models

application = connexion.FlaskApp(__name__)
babel = Babel(application.app)


@application.app.before_request
def before_request():
    initialize.before_request()


@application.app.after_request
def add_header(response):
    return initialize.after_request(response)


@application.app.teardown_appcontext
def cleanup(resp_or_exc):
    """When a flask thread terminates, close the database session"""
    if hasattr(g, 'db'):
        g.db.remove()


@babel.localeselector
def get_locale():
    return initialize.get_locale()


if __name__ in ('__main__', 'uwsgi_file_main', 'example.main'):
    initialize.app(application, controllers, models, os.path.dirname(
        os.path.abspath(__file__)), func_send=send_contact.delay)
if __name__ == '__main__':
    application.run(port=ServiceConfig().config.APP_PORT)
