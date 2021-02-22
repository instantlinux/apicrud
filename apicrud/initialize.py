"""initialize.py

created 9-jan-2021 by richb@instantlinux.net
"""
import connexion
from flask import jsonify
from flask_cors import CORS
import logging
import os

from . import grants
from .access import AccessControl
from .const import Constants
from .metrics import Metrics
from .service_config import ServiceConfig


def app(application):
    """Initialize the Flask app defined by openapi.yaml

    Args:
      application (obj): a connexion object
      init_func (function): any other function to call

    Returns:
      obj: Flask app
    """
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
    application.add_error_handler(400, render_status_4xx)
    application.add_error_handler(429, render_status_4xx)
    application.add_error_handler(connexion.ProblemException,
                                  render_problem)
    CORS(application.app,
         resources={r"/api/*": {'origins': config.CORS_ORIGINS}},
         supports_credentials=True)

    AccessControl().load_rbac(config.RBAC_FILE)
    grants.Grants().load_defaults(config.DEFAULT_GRANTS)
    logging.info(dict(action='initialize_app', port=config.APP_PORT))
    return application.app


def render_status_4xx(error):
    """Render function to provide message in dict as required for
    react-admin to display text of message for 4xx error codes

    Args:
      error (obj): the error object with name and description
    """
    Metrics().store('api_errors_total', labels=['code=%s' % error.code])
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
    Metrics().store('api_errors_total', labels=['code=%s' % error.status])
    return jsonify(dict(
        message=error.detail,
        error=dict(status=error.title, code=error.status))), error.status
