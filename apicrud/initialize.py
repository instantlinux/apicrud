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
import redis

from . import database, AccessControl, AccountSettings, Metrics, RateLimit, \
    ServiceConfig, ServiceRegistry, state
from .const import Constants
from .session_manager import SessionManager


def app(application, controllers, models, path, redis_conn=None,
        func_send=None, **kwargs):
    """Initialize the Flask app defined by openapi.yaml: first four
    params must be passed from main; optional params here support
    configuration and the unit-test framework.

    Args:
      application (obj): a connexion object
      controllers (obj): all controllers
      models (obj): all models
      path (str): location of configuration .yaml / i18n files
      func_send (obj): application's function to send messages
      redis_conn (obj): connection to redis
      kwargs (dict): additional settings for ServiceConfig

    Returns:
      obj: Flask app
    """
    config = ServiceConfig(
        babel_translation_directories='i18n;%s' % os.path.join(path, 'i18n'),
        file=os.path.join(path, 'config.yaml'), models=models,
        reset=True, **kwargs).config
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
    state.config = config
    state.func_send = func_send
    state.models = models
    state.oauth['init'] = OAuth(application.app)
    state.redis_conn = redis_conn or redis.Redis(
        host=config.REDIS_HOST, port=config.REDIS_PORT, db=0)
    ServiceRegistry().register(controllers.resources())
    if database.initialize_db(db_url=config.DB_URL, redis_conn=redis_conn):
        Metrics().store(
            'api_start_timestamp', value=int(datetime.now().timestamp()))
    AccessControl().load_rbac(config.RBAC_FILE)
    for provider in config.AUTH_PARAMS.keys():
        client_id = os.environ.get('%s_CLIENT_ID' % provider.upper())
        client_secret = os.environ.get('%s_CLIENT_SECRET' % provider.upper())
        if client_id:
            state.oauth['init'].register(name=provider, client_id=client_id,
                                         client_secret=client_secret,
                                         **config.AUTH_PARAMS[provider])
            logging.info(dict(action='initialize', provider=provider))

    logging.info(dict(action='initialize_app', port=config.APP_PORT))
    return application.app


def before_request():
    """flask session setup - database and metrics"""
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
    """flask headers and metrics - all responses get a cache-control header"""
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


def get_locale():
    """flask locale"""
    acc = AccessControl()
    if acc.auth and acc.uid:
        locale = AccountSettings(acc.account_id,
                                 uid=acc.uid, db_session=g.db).locale
        if locale:
            return locale
    return request.accept_languages.best_match(
        ServiceConfig().config.LANGUAGES)


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
