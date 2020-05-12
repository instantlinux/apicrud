# Utilities

import connexion
from datetime import datetime
from flask import g, jsonify
from flask_cors import CORS
from html.parser import HTMLParser
import logging
import random
import string

from . import grants, utils
from .access import AccessControl


def gen_id(length=8, prefix='x-', chars=(
        '-' + string.digits + string.ascii_uppercase + '_' +
        string.ascii_lowercase)):
    """Record IDs are random 48-bit RFC-4648 radix-64 with a fixed prefix
    to make them (somewhat) more human-recognizable

    First 15 bits are generated from Unix epoch to make them sortable
    by date (granularity 24 hours); rolls over after year 2107
    """
    def _int2base(x, chars, base=64):
        return _int2base(x // base, chars, base).lstrip(chars[0]) + chars[
            x % base] if x else chars[0]
    return (prefix +
            _int2base((utcnow() - datetime(2018, 1, 1)).days * 8 +
                      random.randint(0, 8), chars) +
            ''.join(random.choice(chars) for i in range(length - 3)))


def initialize_app(application, config, models):
    """ Initialize the Flask app defined by openapi.yaml

    params:
      application - a connexion object
      config - a flask config object
      models - the SQLalchemy models
      init_func - any other function to call
    """

    logging.basicConfig(level=config.LOG_LEVEL,
                        format='%(asctime)s %(levelname)s %(message)s',
                        datefmt='%m-%d %H:%M:%S')
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    application.app.config.from_object(config)
    application.add_api(config.OPENAPI_FILE)
    application.add_error_handler(400, utils.render_status_400)
    application.add_error_handler(connexion.ProblemException,
                                  utils.render_problem)
    CORS(application.app,
         resources={r"/api/*": {'origins': config.CORS_ORIGINS}},
         supports_credentials=True)
    AccessControl().load_rbac(config.RBAC_FILE)
    grants.Grants(models).load_defaults(config.DEFAULT_GRANTS)
    logging.info(dict(action='initialize_app', port=config.PORT))
    return application.app


def render_status_400(error):
    return jsonify(dict(
        message=error.description,
        error=dict(status=error.name, code=error.code))), error.code


def render_problem(error):
    return jsonify(dict(
        message=error.detail,
        error=dict(status=error.title, code=error.status))), error.status


def req_duration():
    return '%.3f' % (utcnow().timestamp() -
                     g.request_start_time.timestamp())


def utcnow():
    """ for mocking: unittest.mock can't patch out datetime.utcnow directly """
    return datetime.utcnow()


def strip_tags(html):
    """Convert html to plain-text by stripping tags"""
    s = HtmlStripper()
    s.feed(html)
    return s.get_data()


class HtmlStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ' '.join(self.fed)
