"""health.py

created 23-sep-2019 by richb@instantlinux.net
"""
from apicrud import health, ServiceConfig

from example import _version
from models import AlembicVersion


class HealthController(object):
    """Healthcheck endpoint - return a standardized status check"""

    @staticmethod
    def get(tests=None):
        """Pass application-specific parameters to the healthcheck
        function

        Returns:
          tuple:
            first element is a dict containing health check report,
            with optional tests, in format recommended by
            Nadareishvili in RFC draft
            https://tools.ietf.org/id/draft-inadarei-api-health-check-04.html;
            second element is http response code
        """
        config = ServiceConfig().config
        return health.healthcheck(
            app_name=config.APPNAME, service_name=config.SERVICE_NAME,
            tests=tests, model=AlembicVersion,
            releaseId=_version.vcs_ref, build_date=_version.build_date,
            version=_version.__version__)
