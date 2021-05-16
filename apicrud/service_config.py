"""service_config.py

created 12-aug-2020 by docker@instantlinux.net
"""
import binascii
from collections import namedtuple
from flask_babel import gettext as _
import jsonschema
import logging
import os
import yaml

from .const import Constants

state = {}
config = None


class ServiceConfig(object):
    """Service configration - have it your way!

    Flask and application configuration global default values are defined in
    service_config.yaml here in the source directory. Overrides of these
    values can be specified in a few ways and are evaluated in this order:

    - Environment variables set by parent process
    - Values defined in a file in yaml format
    - Values passed as a keyword arg at first class invocation

    For runtime security, the config singleton is stored as an immutable
    namedtuple: to change values, update settings and restart the
    container running the service.

    An endpoint /config/v1/config provides read-only access to these values
    except those of type password.  Always override those secret values
    before deploying your service.

    Attribute keys specified as env vars are UPPERCASE, and attribute keys
    stored in the config object are also uppercase. Use lowercase to
    specify attribute keys in kwargs or the yaml input file.

    Args:
      file (str): path of a YAML file defining override values
      models (obj): sqlalchemy db models
      reset (boolean): reset cached values (for unit tests)
      **kwargs: key=value pair arguments to override values

    Raises:
      AttributeError if unrecognized or invalid schema
    """

    def __init__(self, file=None, models=None, reset=False, **kwargs):
        global config

        if reset or not config:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   Constants.SERVICE_CONFIG_FILE), 'rt',
                      encoding='utf8') as f:
                openapi = yaml.safe_load(f)
            overrides = {}
            if file:
                with open(file, 'rt', encoding='utf8') as f:
                    overrides = yaml.safe_load(f)
                if not overrides:
                    raise AttributeError('No values found in %s' % file)

            for key, schema in openapi['components']['schemas'][
                    'Config']['properties'].items():
                if os.environ.get(key.upper()):
                    if schema['type'] == 'array':
                        state[key] = os.environ[key.upper()].split(',')
                    elif schema['type'] == 'integer':
                        state[key] = int(os.environ[key.upper()])
                    elif schema['type'] == 'boolean':
                        if os.environ[
                                key.upper()].lower() in ('1', 'true', 'yes'):
                            state[key] = True
                        elif os.environ[
                                key.upper()].lower() in ('0', 'false', 'no'):
                            state[key] = False
                        else:
                            raise AttributeError('Invalid value for %s' % key)
                    else:
                        state[key] = os.environ[key.upper()]
                    overrides.pop(key, None)
                elif key in overrides:
                    if schema['type'] == 'object':
                        state[key] = schema['default']
                        state[key].update(overrides.pop(key))
                    else:
                        state[key] = overrides.pop(key)
                elif key in kwargs:
                    state[key] = kwargs[key]
                elif 'default' in schema:
                    state[key] = schema['default']
                elif key == 'db_url':
                    state[key] = self._compose_db_url()
                else:
                    raise AttributeError('No value specified for %s' % key)
            jsonschema.validate(instance=state, schema=openapi['components'][
                'schemas']['Config'])
            if overrides:
                raise AttributeError(
                    'ServiceConfig: unrecognized entries %s' %
                    ','.join(overrides))
            # Special cases
            state['secret_key'] = binascii.unhexlify(
                state['flask_secret_key'])
            state['metrics'] = self._compose_metrics(state['metrics'])
            state['log_level'] = self._compose_loglevel(state['log_level'])
            state['template_folders'].append(
                    os.path.join(os.path.dirname(__file__), 'templates'))
            if os.environ.get('APP_ENV') != 'prod':
                state['login_admin_limit'] = max(
                    state['login_admin_limit'], 86400)
                state['login_session_limit'] = max(
                    state['login_admin_limit'], 86400)
            if '/' not in state['babel_translation_directories'].split(';')[0]:
                state['babel_translation_directories'] = (
                    os.path.join(os.path.dirname(__file__),
                                 state['babel_translation_directories']))
            if file:
                if '/' not in state['rbac_file']:
                    state['rbac_file'] = os.path.join(os.path.dirname(
                        os.path.abspath(file)), state['rbac_file'])
                if '/' not in state['db_migrations']:
                    state['db_migrations'] = os.path.join(os.path.dirname(
                        os.path.abspath(file)), state['db_migrations'])
                if '/' not in state['db_seed_file']:
                    state['db_seed_file'] = os.path.join(os.path.dirname(
                        os.path.abspath(file)), state['db_seed_file'])
            state.pop('schema', None)
            state.pop('models', None)
            config = namedtuple('Struct', [
                key.upper() for key in state.keys()])(*state.values())
            state['schema'] = openapi['components']['schemas']['Config']

        if models:
            state['models'] = models
        self.models = state.get('models')
        self.config = config

    @staticmethod
    def _compose_db_url():
        return (
            '%(dbtype)s://%(user)s:%(password)s@%(endpoint)s/%(database)s' %
            {'dbtype': os.environ.get('DB_TYPE', 'mysql+pymysql'),
             'user': os.environ.get('DB_USER', 'example'),
             'password': os.environ.get('DB_PASS', 'example'),
             'endpoint': '%s:%d' % (os.environ.get('DB_HOST'),
                                    int(os.environ.get('DB_PORT', 3306))),
             'database': os.environ.get('DB_NAME', 'example')})

    @staticmethod
    def _compose_loglevel(level):
        """Convert a string 'info' to the enum logging.INFO

        Args:
            level (str): debug, info, warning, error or critical
        """
        return dict(
            debug=logging.DEBUG, info=logging.INFO, warning=logging.WARNING,
            error=logging.ERROR, critical=logging.CRITICAL)[level]

    @staticmethod
    def _compose_metrics(metrics):
        """Fill in default values for scope, style, period

        Args:
            metrics (dict): usage metric definitions
                period: hour, day, week, month, indefinite
                scope: user, instance, sitewide
                style: grant, usage
        """
        ret = metrics
        for key, item in metrics.items():
            if set(item.keys()) - set(['notify', 'period', 'scope', 'style']):
                raise AttributeError('Invalid metric configuration')
            ret[key]['notify'] = item.get('notify', 0)
            ret[key]['period'] = item.get('period', 'day')
            ret[key]['scope'] = item.get('scope', 'user')
            ret[key]['style'] = item.get('style', 'grant')
        return ret

    @staticmethod
    def get():
        from .access import AccessControl

        if not AccessControl().auth or 'admin' not in AccessControl().auth:
            return dict(message=_(u'access denied')), 403
        retval = {key: state[key]
                  for key, props in state['schema']['properties'].items()
                  if key not in ('db_url') and
                  ('format' not in props or props['format'] != 'password')}
        return retval, 200
