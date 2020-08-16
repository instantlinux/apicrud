"""service_config.py

Service Config
  Flask and application configuration global defaults are defined in
  service_config.yaml. Overrides of defaults are evaluated in this
  order:

  - Values passed as a keyword arg at first class invocation
  - Values defined in a file in yaml format
  - Environment variables set by parent process

  For security, the config singleton is stored as an immutable
  namedtuple: to change values, update settings and restart the
  container running the service.

  An endpoint /config/v1/config provides read-only access to these values
  except those of type password.  Always override those secret values
  before deploying your service.

  Attribute keys specified as env vars are UPPERCASE, and attribute keys
  stored in the config object are also uppercase. Use lowercase to
  specify attribute keys in kwargs or the yaml input file.

created 12-aug-2020 by docker@instantlinux.net
"""

import binascii
from collections import namedtuple
import jsonschema
import logging
import os
import yaml

from .const import Constants

state = {}
config = None


class ServiceConfig(object):
    """Service config for flask application

    Attributes:
      file (str): path of a YAML file defining override values
      models (obj): sqlalchemy db models
      reset (boolean): reset cached values (for unit tests)
      **kwargs: key=value pair arguments to override values

    Raises:
      AttributeError if invalid specification
    """

    def __init__(self, file=None, models=None, reset=False, **kwargs):
        global config

        if reset or not config:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   Constants.SERVICE_CONFIG_FILE), 'r') as f:
                openapi = yaml.safe_load(f)

            overrides = {}
            if file:
                with open(file, 'r') as f:
                    overrides = yaml.safe_load(f)
                if not overrides:
                    raise AttributeError('No values found in %s' % file)

            for key, schema in openapi['components']['schemas'][
                    'Config']['properties'].items():
                if key in kwargs:
                    state[key] = kwargs[key]
                elif key in overrides:
                    state[key] = overrides[key]
                elif os.environ.get(key.upper()):
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
                elif 'default' in schema:
                    state[key] = schema['default']
                elif key == 'db_url':
                    state[key] = self._compose_db_url()
                else:
                    raise AttributeError('No value specified for %s' % key)
            jsonschema.validate(instance=state, schema=openapi['components'][
                'schemas']['Config'])
            # Special cases
            state['flask_secret_key'] = binascii.unhexlify(
                state['flask_secret_key'])
            state['log_level'] = self._compose_loglevel(state['log_level'])
            if os.environ.get('APP_ENV') != 'prod':
                state['login_admin_limit'] = max(
                    state['login_admin_limit'], 86400)
                state['login_session_limit'] = max(
                    state['login_admin_limit'], 86400)
            if file and '/' not in state['rbac_file']:
                state['rbac_file'] = os.path.join(os.path.dirname(
                    os.path.abspath(file)), state['rbac_file'])

            config = namedtuple('Struct', [key.upper() for key in
                                           state.keys()])(*state.values())
            state['schema'] = openapi['components']['schemas']['Config']
            state['models'] = models
        self.config = config
        self.models = state['models']

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

    def set(self, key, value):
        """Set a single value

        Args:
            key (str) - attribute name
            value - new value
        """
        global config

        jsonschema.validate(instance={key: value}, schema=state['schema'])
        state[key] = value
        config = namedtuple('Struct', [key.upper() for key in
                                       state.keys()])(*state.values())

    @staticmethod
    def get():
        from .access import AccessControl

        if not AccessControl().auth or 'admin' not in AccessControl().auth:
            return dict(message='access denied'), 403
        retval = {key: state[key]
                  for key, props in state['schema']['properties'].items()
                  if key not in ('db_url') and
                  ('format' not in props or props['format'] != 'password')}
        return retval, 200