"""metric controller

created 27-may-2019 by richb@instantlinux.net
"""

from apicrud import BasicCRUD, Metrics


class MetricController(BasicCRUD):
    def __init__(self):
        self.resource = 'metric'

    @staticmethod
    def find(**kwargs):
        """Find multiple metrics

        Args:
            kwargs: as defined in openapi.yaml
        """
        return Metrics().find(**kwargs)

    @staticmethod
    def collect(**kwargs):
        """Collect metrics in prometheus-compatible format

        Args:
            kwargs: as defined in openapi.yaml
        """
        return Metrics().collect(**kwargs)
