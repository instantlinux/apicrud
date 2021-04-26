"""initialize.py

created 9-jan-2021 by richb@instantlinux.net
"""
from authlib.integrations.flask_client import OAuth
import connexion
from datetime import datetime
from flask import abort, g, jsonify, request
from flask_cors import CORS
import logging
import os

from . import database, AccessControl, Metrics, RateLimit, \
    ServiceConfig, ServiceRegistry
from .const import Constants
from .session_manager import SessionManager

oauth = {}
params = {}


def app(application, controllers, models, path, redis_conn=None,
        db_url=None, db_seed_file=None, func_send=None):
    """Initialize the Flask app defined by openapi.yaml

    Args:
      application (obj): a connexion object
      controllers (obj): all controllers
      models (obj): all models
      path (str): location of configuration .yaml / i18n files
      init_func (function): any other function to call
      db_seed_file (filename): database records in yaml format
      func_send (obj): application's function to send messages

    Returns:
      obj: Flask app
    """
    global oauth, params

    config = ServiceConfig(
        babel_translation_directories='i18n;%s' % os.path.join(path, 'i18n'),
        db_seed_file=db_seed_file, file=os.path.join(path, 'config.yaml'),
        models=models, reset=True).config
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
    params = dict(func_send=func_send, models=models, redis_conn=redis_conn)
    ServiceRegistry(redis_conn=redis_conn).register(controllers.resources())
    if database.initialize_db(db_url=db_url, redis_conn=redis_conn):
        Metrics(redis_conn=redis_conn, func_send=func_send).store(
            'api_start_timestamp', value=int(datetime.now().timestamp()))
    AccessControl().load_rbac(config.RBAC_FILE)
    oauth['init'] = OAuth(application.app)
    for provider in config.AUTH_PARAMS.keys():
        client_id = os.environ.get('%s_CLIENT_ID' % provider.upper())
        client_secret = os.environ.get('%s_CLIENT_SECRET' % provider.upper())
        if client_id:
            oauth['init'].register(name=provider, client_id=client_id,
                                   client_secret=client_secret,
                                   **config.AUTH_PARAMS[provider])
            logging.info(dict(action='initialize', provider=provider))

    logging.info(dict(action='initialize_app', port=config.APP_PORT))
    return application.app


def before_request():
    """flask session setup - database and metrics
    """
    g.db = database.get_session()
    g.session = SessionManager()
    g.request_start_time = datetime.utcnow()
    try:
        resource = request.url_rule.rule.split('/')[3]
    except Exception:
        resource = None
    if resource != 'metrics':
        Metrics().store('api_calls_total', labels=['resource=%s' % resource])
    if request.method != 'OPTIONS' and RateLimit().call():
        Metrics().store('api_errors_total', labels=['code=%d' % 429])
        abort(429)


def after_request(response):
    """All responses get a cache-control header"""
    config = ServiceConfig().config
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
