"""health.py

created 28-mar-2020 by richb@instantlinux.net
"""

from flask import g

from ._version import __version__


def healthcheck(app_name='api', service_name='main', tests=None, model=None,
                releaseId=None, build_date=None, version=None):
    """Support for a standardized healthcheck endpoint - returns a
    health check report, with optional tests, in format recommended by
    Nadareishvili in RFC draft
    https://tools.ietf.org/id/draft-inadarei-api-health-check-04.html

    Args:
      app_name (str): the application name for description
      service_name (str): microservice name for serviceId
      tests (list): optional tests to run
      model (obj): schema model (usually AlembicVersion)
      releaseId (str): a release ID string
      build_date (str): build timestamp
      version (str): a version string
    Returns:
      tuple: first element is pass or fail, second is response code
    """

    status = 200
    retval = dict(
        description="%s - %s" % (app_name, service_name),
        notes=["build_date:%s" % build_date],
        serviceId=service_name)
    if releaseId:
        retval['releaseId'] = releaseId
    if version:
        retval['version'] = version
    if model:
        try:
            retval['notes'].append(
                'schema:%s' % g.db.query(model).one().version_num)
            retval['notes'].append(
                'apicrud_version:%s' % __version__)
        except Exception as ex:
            retval['output'] = str(ex)
            status = 503
    return dict(
        status="pass" if status == 200 else "fail", **retval), status
