"""metrics.py

Metrics and usage tracking

created 21-feb-2021 by richb@instantlinux.net
"""

from flask_babel import _
import json
import logging
import os

from . import state
from .access import AccessControl
from .const import Constants
from .grants import Grants
from .service_config import ServiceConfig
from .service_registry import ServiceRegistry

INTERVALS = dict(hour=3600, day=3600 * 24, week=3600 * 24 * 7,
                 month=3600 * 24 * 31, indefinite=None)


class Metrics(object):
    """This implementation supports standard system metrics and two types of
    usage-billing: granted limits per period, or metered usage.

    See this article for a description of how redis makes the implementation
    straightforward:
    https://www.infoworld.com/article/3230455/how-to-use-redis-for-real-time-metering-applications.html
    The data store is in-memory, with snapshot/append persistence to disk.

    All metrics are defined in the metrics section of service_config.yaml.
    These follow a de facto standard described in best-practices
    documentation section of prometheus.io website. At time of implementation,
    flask prometheus client is not mature/user-friendly enough or
    suitable for usage-billing so to keep this consistent with
    service_config.yaml, there is no intent now or in the future to
    use it.

    Thanks to the expiring keys feature of redis, grant limits can be
    implemented without any periodic cleanup task. Upon first use,
    a decrementing key is created with expiration set to the configured period.
    If it counts down to zero before expiration (for example, 50 video uploads
    per day), the user is denied access to the resource until the key expires.
    If a user never returns, there will be no redis keys consuming system
    resources unless and until the user comes back, at which point a new grant
    period starts. Scaling to tens of millions of users is practical within a
    small footprint, and this is why user-tracking metrics are stored in redis
    rather than a traditional database.

    Attributes:
      uid (str): ID of a user, for usage tracking
      db_session (obj): existing db connection
      func_send (obj): function name for sending message via celery
    """
    def __init__(self, uid=None, db_session=None, func_send=None):
        self.config = config = ServiceConfig().config
        self.connection = state.redis_conn
        self.db_session = db_session
        self.func_send = state.func_send = func_send or state.func_send
        self.metrics = config.METRICS
        self.uid = uid

    def store(self, name, labels=[], value=None):
        """Store a metric: redis keys are in form mtr:<name>:<labels>
        To avoid possible ambiguity and multiple redis keys for the same
        label set, this function sorts labels before storing.

        Params:
          name (str): a metric name
          labels (list): labels, usually in form <label>=<value>
          value (int or float): value to store

        Returns:
          bool: true in all cases except for grant exceeded
        """
        if name not in self.metrics:
            raise AssertionError('name=%s not defined in config' % name)

        metric = self.metrics[name]
        if not labels:
            if metric['scope'] == 'instance':
                labels = ['instance=%s' % ServiceRegistry().get()['id']]
            else:
                labels = ['uid=%s' % self.uid] if self.uid else []
        labels.sort()
        key = 'mtr:%s:%s' % (name, ",".join(labels))
        if metric['style'] == 'grant':
            current = self.connection.get(key)
            limit = Grants(db_session=self.db_session).get(name, uid=self.uid)
            if current is None or int(current) >= limit:
                self.connection.set(key, limit - 1,
                                    ex=INTERVALS[metric['period']])
            elif int(current) <= 0:
                return False
            else:
                if metric['notify'] and self.func_send:
                    used = float(current) / limit * 100
                    used_next = (float(current) - 1.0) / limit * 100
                    if ((used >= 100 - metric['notify']) and
                            (used_next < 100 - metric['notify'])):
                        self.func_send(
                            to_uid=self.uid, template='usage_notify',
                            percent=metric['notify'], period=metric['period'],
                            resource=name)
                self.connection.decr(key)
        elif metric['style'] == 'counter':
            if type(value) is int:
                self.connection.incrby(key, value)
            elif type(value) is float:
                self.connection.incrbyfloat(key, value)
            elif value is None:
                self.connection.incr(key)
            else:
                raise AssertionError('Invalid value')
        elif metric['style'] == 'gauge':
            self.connection.set(key, value)
        return True

    def check(self, name):
        """Check remaining credit against grant-style metric

        Params:
          name (str): a metric name

        Returns:
          float: amount of credit remaining, or None
        """
        if name not in self.metrics:
            raise AssertionError('name=%s not defined in config' % name)

        metric = self.metrics[name]
        labels = ['uid=%s' % self.uid] if self.uid else []
        key = 'mtr:%s:%s' % (name, ",".join(labels))
        if metric['style'] != 'grant':
            raise AssertionError('name=%s is not a grant metric' % name)

        current = self.connection.get(key)
        limit = Grants(db_session=self.db_session).get(name, uid=self.uid)
        if current is None or float(current) >= limit:
            return float(limit)
        elif float(current) > 0:
            return float(current)
        return None

    def find(self, **kwargs):
        """Look up metrics defined by filter

        Returns:
          tuple (results dict, status)
        """
        try:
            filter = json.loads(kwargs.get('filter', '{}'))
        except json.decoder.JSONDecodeError as ex:
            logmsg = dict(action='find', resource='metric')
            msg = _(u'invalid filter specified') + '=%s' % str(ex)
            logging.error(dict(message=msg, **logmsg))
            return dict(message=msg), 405
        name = filter.get('name') or kwargs.get('name', '*')
        acc = AccessControl()
        auth = acc.auth
        if 'admin' in auth:
            if 'uid' in filter or 'uid' in kwargs:
                uid = filter.get('uid') or kwargs.get('uid')
                label = 'uid=%s' % uid if uid else 'uid=*'
            else:
                label = filter.get('label') or kwargs.get('label', '*')
                if label != '*':
                    label = '*%s*' % label
            self._process_collect()
        elif 'user' in auth:
            uid = filter.get('uid')
            if not uid or uid != acc.uid:
                return dict(message=_(u'access denied')), 403
            label = 'uid=%s' % uid
        else:
            return dict(message=_(u'access denied')), 403
        key = 'mtr:%s:%s' % (name, label)
        limit = kwargs.get('limit', Constants.PER_PAGE_DEFAULT)
        offset = kwargs.get('offset', 0)
        count, retval = 0, []
        for item in self.connection.scan_iter(match=key):
            if offset:
                offset -= 1
            else:
                value = self.connection.get(item).decode()
                try:
                    value = int(value)
                except ValueError:
                    value = float(value)
                retval.append(dict(
                    name=item.decode().split(':')[1],
                    labels=item.decode().split(':')[2].split(','),
                    value=value))
            count += 1
            if count >= limit:
                break
        return dict(items=retval, count=count), 200

    def collect(self, **kwargs):
        """
        Prometheus-compatible metrics exporter. Collects current
        metrics from redis, evaluates metric-type settings in
        service_config.yaml, and returns a plain-text result in this form:

        # TYPE process_resident_memory_bytes gauge
        process_resident_memory_bytes{instance="k8s-01.ci.net"} 20576.0
        # TYPE process_start_time_seconds gauge
        process_start_time_seconds{instance="k8s-01.ci.net"} 1614051156.14
        # TYPE api_calls_total counter
        api_calls_total{resource="person"} 4
        """
        try:
            filter = json.loads(kwargs.get('filter', '{}'))
        except json.decoder.JSONDecodeError as ex:
            logmsg = dict(action='find', resource='metric')
            msg = _(u'invalid filter specified') + '=%s' % str(ex)
            logging.error(dict(message=msg, **logmsg))
            return dict(message=msg), 405
        name = filter.get('name') or kwargs.get('name', '*')
        if 'uid' in filter:
            uid = filter.get('uid', '*')
            label = 'uid=%s' % uid if uid else 'uid=*'
        else:
            label = filter.get('label') or kwargs.get('label', '*')
            if label != '*':
                label = '*%s*' % label
        self._process_collect()
        key = 'mtr:%s:%s' % (name, label)
        limit = kwargs.get('limit', Constants.PER_PAGE_DEFAULT)
        count, retval = 0, []
        for item in self.connection.scan_iter(match=key):
            name = item.decode().split(':')[1]
            if name not in self.metrics:
                continue
            type_ = self.metrics[name]['style']
            if type_ == 'grant':
                # TODO decide better way to filter out style=grant
                if 'uid' not in label:
                    continue
                type_ = 'gauge'
            retval.append(dict(name=name, type_=type_,
                               labels=item.decode().split(':')[2].split(','),
                               value=self.connection.get(item).decode()))
            count += 1
            if count >= limit:
                break
        output = ""
        for item in retval:
            output += "# TYPE %s %s\n" % (item['name'], item['type_'])
            labels = ['%s="%s"' % (label.split('=')[0], label.split('=')[1])
                      if '=' in label else label
                      for label in item['labels']]
            output += "%s%s %s\n" % (
                item['name'],
                '{%s}' % ','.join(labels) if labels else '', item['value'])
        return output, 200

    def _process_collect(self):
        """Collect metrics for process_xxx"""

        proc = '/proc/self'
        boot_timestamp = self._boot_time()
        if not boot_timestamp:
            return None
        with open('%s/stat' % proc, 'rb') as stat:
            # https://man7.org/linux/man-pages/man5/procfs.5.html
            #  subtract 3 from index values documented in /proc/[pid]/stat
            #  we use utime, stime, starttime, vsize and rss
            stats = (stat.read().split(b')')[-1].split())
        try:
            with open('%s/limits' % proc, 'rb') as fp:
                for line in fp:
                    if line.startswith(b'Max open files'):
                        max_fds = int(line.split()[3])
        except (IOError, OSError):
            max_fds = 0
        try:
            ticks = os.sysconf('SC_CLK_TCK')
        except (ValueError, TypeError, AttributeError, OSError):
            ticks = 100.0

        self.store('process_cpu_seconds_total',
                   value=(float(stats[11]) + float(stats[12])) / ticks)
        self.store('process_max_fds', value=max_fds)
        self.store('process_open_fds', value=len(os.listdir('%s/fd' % proc)))
        self.store('process_resident_memory_bytes', value=float(stats[21]))
        self.store('process_start_time_seconds',
                   value=boot_timestamp + float(stats[19]) / ticks)
        self.store('process_virtual_memory_bytes', value=float(stats[20]))

    @staticmethod
    def _boot_time():
        try:
            with open('/proc/stat', 'rb') as fp:
                for line in fp:
                    if line.startswith(b'btime '):
                        return float(line.split()[1])
        except IOError:
            return None
