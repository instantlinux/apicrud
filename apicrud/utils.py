"""utilities.py

Utilities
  Miscellaneous utility functions that don't fit elsewhere

created 11-apr-2020 by richb@instantlinux.net
"""
import connexion
from datetime import datetime
from flask import g, jsonify
from flask_babel import _
from flask_cors import CORS
from html.parser import HTMLParser
import logging
import os
import random
import string

from . import grants
from .access import AccessControl
from .const import Constants
from .service_config import ServiceConfig


def gen_id(length=8, prefix='x-', chars=(
        '-' + string.digits + string.ascii_uppercase + '_' +
        string.ascii_lowercase)):
    """Record IDs are random 48-bit RFC-4648 radix-64 with a fixed prefix
    to make them (somewhat) more human-recognizable

    First 15 bits are generated from Unix epoch to make them sortable
    by date (granularity 24 hours); rolls over after year 2107

    Args:
      length (int): length of generated portion after prefix
      prefix (str): prefix to distinguish ID type
      chars (str): set of characters to choose from for random portion
    """
    def _int2base(x, chars, base=64):
        return _int2base(x // base, chars, base).lstrip(chars[0]) + chars[
            x % base] if x else chars[0]
    return (prefix +
            _int2base((utcnow() - datetime(2018, 1, 1)).days * 8 +
                      random.randint(0, 8), chars) +
            ''.join(random.choice(chars) for i in range(length - 3)))


def initialize_app(application):
    """Initialize the Flask app defined by openapi.yaml

    Args:
      application (obj): a connexion object
      init_func (function): any other function to call

    Returns:
      obj: Flask app
    """
    global babel

    config = ServiceConfig().config
    logging.basicConfig(level=config.LOG_LEVEL,
                        format='%(asctime)s %(levelname)s %(message)s',
                        datefmt='%m-%d %H:%M:%S')
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    application.app.config.from_object(config)
    application.add_api(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     Constants.SERVICE_CONFIG_FILE), base_path='/config/v1')
    application.add_api(config.OPENAPI_FILE)
    application.add_error_handler(400, render_status_400)
    application.add_error_handler(connexion.ProblemException,
                                  render_problem)
    CORS(application.app,
         resources={r"/api/*": {'origins': config.CORS_ORIGINS}},
         supports_credentials=True)
    AccessControl().load_rbac(config.RBAC_FILE)
    grants.Grants().load_defaults(config.DEFAULT_GRANTS)
    logging.info(dict(action='initialize_app', port=config.APP_PORT))
    return application.app


def render_status_400(error):
    """Render function to provide message in dict as required for
    react-admin to display text of message for 400 error codes

    Args:
      error (obj): the error object with name and description
    """

    return jsonify(dict(
        message=error.description,
        error=dict(status=error.name, code=error.code))), error.code


def render_problem(error):
    """Render function to provide message in dict as required for
    react-admin to display text of message for exception
    connexion.ProblemException

    Args:
      error (obj): the error object with name and description
    """

    return jsonify(dict(
        message=error.detail,
        error=dict(status=error.title, code=error.status))), error.status


def req_duration():
    """Report request duration as milliseconds """

    return '%.3f' % (utcnow().timestamp() -
                     g.request_start_time.timestamp())


def utcnow():
    """For mocking: unittest.mock can't patch out datetime.utcnow directly """
    return datetime.utcnow()


def strip_tags(html):
    """Convert html to plain-text by stripping tags

    Args:
      html (str): an html document
    """

    s = HtmlStripper()
    s.feed(html)
    return s.get_data()


def replace_last_comma_and(string):
    """Replace the last comma with the word 'and', dealing with
    translation.  The string is presumed to be a text array joined by
    ', ' -- including the space.

    Args:
        string (str): comma-separated utf8 content
    """

    i = string.rfind(',')
    if i == -1:
        return string
    else:
        return string[:i] + ' ' + _(u'and') + string[i + 1:]


class HtmlStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []

    def handle_data(self, d):
        """ add a string to the html object

        Args:
          d (str): chunk of html
        """
        self.fed.append(d)

    def get_data(self):
        """ return the stripped html

        Returns: str
        """
        return ' '.join(self.fed)
