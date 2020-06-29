"""health.py

created 23-sep-2019 by richb@instantlinux.net
"""

from example import _version
import config
from apicrud import health
from models import AlembicVersion


class HealthController(object):
    @staticmethod
    def get(tests=None):
        return health.healthcheck(
            app_name=config.APPNAME, service_name=config.SERVICE_NAME,
            tests=tests, model=AlembicVersion,
            releaseId=_version.vcs_ref, build_date=_version.build_date,
            version=_version.__version__)
