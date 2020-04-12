"""health.py

created 28-mar-2020 by richb@instantlinux.net
"""

from flask import g


def healthcheck(app_name='api', service_name='main', tests=None, model=None,
                releaseId=None, build_date=None, version=None):
    """Returns a health check report, with optional tests, in
    format recommended by Nadareishvili in RFC draft
    https://tools.ietf.org/id/draft-inadarei-api-health-check-04.html

    params:
      service_name - microservice name for serviceId
      tests - optional tests to run
      model - schema model (usually AlembicVersion)
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
        except Exception as ex:
            retval['output'] = str(ex)
            status = 503
    return dict(
        status="pass" if status == 200 else "fail", **retval), status
