"""health.py

created 23-sep-2019 by richb@instantlinux.net
"""

import _version
from apicrud import health
import config
from models import AlembicVersion


class HealthController(object):
    @staticmethod
    def get(tests=None):
        return health.healthcheck(
            app_name=config.APPNAME, tests=tests, model=AlembicVersion,
            releaseId=_version.vcs_ref, build_date=_version.build_date,
            version=_version.__version__)
