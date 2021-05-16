"""access.py

created 20-may-2019 by richb@instantlinux.net
refactored 6-mar-2020
"""

from base64 import b64encode
from datetime import timedelta
from flask import g, request
from flask_babel import _
import hashlib
import logging
import re
from sqlalchemy import or_
from sqlalchemy.orm.exc import NoResultFound
import yaml

from . import state
from .service_config import ServiceConfig
from .utils import gen_id, utcnow

LEVELS = {}
POLICIES = {}


class AccessControl(object):
    """Role-based access control

    Definitions:

    - principal: a user or role
    - membership: parent resource type for privacy sharing
    - model: database model name (e.g. Person)
    - resource: resource type (e.g. person)
    - rbac: role-based access control (defined in rbac.yaml)
    - role: a group name (e.g. admin or list-<id>-<level>)
    - privacy: sharing options as defined in rbac.yaml (e.g. \
      secret [default], public, invitee, member, manager)
    - actions: crudlghij (create, read, update, del, list, guest/member, \
      host/manager, invitee, join)

    In rbac.yaml, define the RBAC policies for each principal/resource
    combination. That file will be parsed into a singleton variable upon
    initial startup.  This implementation implements RBAC similar to that of
    kubernetes or AWS IAM, with the added capability of a simple privacy
    permission within each object (database record) which creates an implied
    ACL for read-only access by members of the object's group.

    Group names currently used are:

    - admin
    - user
    - pending (new-account confirmation)
    - pendingtotp
    - person
    - <resource>-<id>-<privacy>

    These are defined in session_auth.py's account_login() method.

    One resource can be used to define user's group memberships with a
    rbac.yaml entry in this form:

    private_resources:
      - resource: list
        attr: list_id

    A user who is a member of list "wildlife-lovers" which has an id
    x-12345678 would get an auth role "list-x-12345678-member".

    Args:
      policy_file (str): name of the yaml definitions file
      model (obj): a model to be validated for permissions
    """
    def __init__(self, policy_file=None, model=None):
        if POLICIES and request:
            self.policies = POLICIES['policies']
            self.privacy_levels = LEVELS['levels']
            self.private_res = state.private_res
            self.model = model
            self.models = ServiceConfig().models
            self.resource = model.__name__.lower() if model else None
            self.auth = self.auth_method = None
            header_auth = ServiceConfig().config.HEADER_AUTH_APIKEY
            self.apikey_id = None
            if header_auth in request.headers:
                # TODO: add support for HMAC request signing in place
                # of this plain-text X-Api-Key header method
                prefix, secret = request.headers.get(header_auth).split('.')
                item = g.session.get(None, self.apikey_hash(secret)[:8],
                                     key_id=prefix)
                if item:
                    self.auth = item.get('auth').split(':')
                    self.uid = uid = item.get('sub')
                    self.apikey_id = prefix
            elif request.authorization:
                uid = self.uid = request.authorization.username
                secret = request.authorization.password
                try:
                    self.auth = g.session.get(
                        uid, secret, arg='auth').split(':')
                except AttributeError:
                    pass
            self.primary_resource = self.private_res[0]['resource']
            self.auth_ids = {self.primary_resource: []}
            if self.auth:
                for role in self.auth:
                    ev = self._parse_id(role, self.primary_resource)
                    if ev:
                        self.auth_ids[self.primary_resource].append(ev)
                self.account_id = g.session.get(uid, secret, 'acc')
                self.auth_method = g.session.get(uid, secret, 'method')
                self.identity = g.session.get(uid, secret, 'identity')
            else:
                # For anonymous-access paths that don't require security
                self.uid = self.account_id = self.identity = None

    def load_rbac(self, filename):
        """ Read RBAC default policies from rbac.yaml, process any
        string substitutions, and convert * for re.match()

        Args:
          filename (str): filename containing RBAC definitions
        """

        with open(filename, 'rt', encoding='utf8') as f:
            rbac = yaml.safe_load(f)
            self.policies = {}
        for res, policy in rbac['policies'].items():
            self.policies[res] = []
            for item in policy:
                self.policies[res].append(dict(
                    principal=item['principal'].format(
                    ).replace('*', '.*'),
                    resource=item['resource'].format(
                        resource=res).replace('*', '.*'),
                    actions=set(list(item['actions']))))
                self.privacy_levels = rbac['privacy_levels']
                self.private_res = rbac.get(
                    'private_resources', [
                        dict(resource='list', attr='list_id')])
                LEVELS['levels'] = self.privacy_levels
                POLICIES['policies'] = self.policies
                state.private_res = self.private_res

    def with_permission(self, access, query=None, new_uid=None,
                        membership=None, id=None):
        """Evaluate permission to access an object identified by
        an open query or new uid. Pass in at least one of the
        query/uid/eid params

        Args:
          access (str): one of lrwcd (list, read, write, create, delete)
          query (obj): a resource query by id in SQLalchemy
          new_uid (str): user id of a new record
          membership (str): resource type which defines membership privacy
          id (str): resource ID

        Returns:
          bool: True if access allowed
        """
        rbac = self.rbac_permissions(query=query, owner_uid=new_uid,
                                     membership=membership, id=id)
        if access in rbac:
            return True
        else:
            duration = (utcnow().timestamp() -
                        g.request_start_time.timestamp())
            logging.info(dict(
                action='with_permission', message=_('access denied'),
                resource=self.resource, uid=self.uid, ident=self.identity,
                access=access, rbac=rbac, duration='%.3f' % duration))
        return False

    def with_filter(self, query, access='r'):
        """Apply RBAC and privacy to a query

        Args:
          query (obj): a resource query in SQLalchemy
          access (str): one of lrwcd (list, read, write, create, delete)

        Returns:
          obj: updated SQLalchemy query with filter applied

        TODO restrictions on contact-read by list-id
        """
        if hasattr(self.model, 'privacy'):
            conditions = [self.model.privacy == 'public']
        else:
            conditions = []
        for policy in self.policies[self.resource]:
            if policy['principal'] == '.*' and access in policy['actions']:
                return query
            if self.auth:
                if (policy['resource'] == '%s:.*' % self.resource and
                        policy['principal'] in self.auth and
                        access in policy['actions']):
                    return query
                elif (policy['resource'] == '%s:{uid}' % self.resource and
                      policy['principal'].split('/')[0] in ('person', 'user')
                      and policy['principal'].split('/')[0] in self.auth and
                      access in policy['actions']):
                    conditions.append(self.model.uid == self.uid)
                    # Special case: add referrer too
                    if self.resource == 'contact':
                        query = query.join(self.models.Person)
                        conditions.append(
                            self.models.Person.referrer_id == self.uid)
                elif (policy['resource'] == '%s:{uid}' % self.resource and
                      access in policy['actions']):
                    for role in self.auth:
                        if re.match(policy['principal'], role):
                            conditions.append(self.model.uid == self.uid)
                            break
        return query.filter(or_(*conditions))

    def rbac_permissions(self, query=None, owner_uid=None, membership=None,
                         id=None, privacy=None):
        """Evaluate an access request for self.auth roles of
        self.uid in self.resource against defined policies

        Args:
          query (obj):  an existing record (takes precedence over owner_uid)
          owner_uid (str): owner-uid of a record
          membership (str): resource type which defines membership privacy
          id (str): the resource ID if membership is set

        Returns:
          set: actions available to principal
        """
        if query:
            try:
                record = query.one()
                if hasattr(record, 'uid'):
                    owner_uid = record.uid
                elif hasattr(record, 'referrer_id'):
                    owner_uid = record.referrer_id or record.id
                if hasattr(record, 'privacy'):
                    privacy = record.privacy
                if hasattr(record, self.private_res[0]['attr']):
                    membership = self.private_res[0]['resource']
                    id = getattr(record, self.private_res[0]['attr'])
            except NoResultFound as ex:
                logging.warning('action=evaluate_rbac message=%s' % str(ex))
        if not id:
            membership = None

        # TODO improve schema or yaml syntax to handle these special-cases
        # TODO make the contact find function return correct rbac
        deny_delete = set()
        if query and self.resource == 'contact':
            if self.uid and self.uid != owner_uid:
                owner_uid = query.one().owner.referrer_id or owner_uid
            # TODO redesign fragile dependency on primary contact
            try:
                g.db.query(self.models.Person).filter_by(
                    identity=query.one().info).one()
                deny_delete = set('d')
            except NoResultFound:
                pass

        actions, defaults = (set(), set())
        if privacy == 'public' or (
                self.auth and id and '%s-%s-%s' % (membership, id, privacy)
                in self.auth):
            # TODO this needs another check that the current resource's
            # id is in fact attached to the record identified by
            # membership and id (which is, say, an event-id)
            defaults = set('r')

        for policy in self.policies[self.resource]:
            if policy['principal'] == '.*':
                defaults = set(list(policy['actions']))
            elif self.auth:
                for role in self.auth:
                    if role in ('person', 'user'):
                        role += '/{uid}'
                    match_id = None
                    # TODO match_id is a bit hacky, should format str
                    if 'uid' in policy['resource']:
                        match_id = self.uid
                    elif 'eid' in policy['resource']:
                        match_id = id

                    # TODO fix the wildcard matching
                    if (policy['principal'].format(eid=id, list_id=id,
                                                   uid=owner_uid) ==
                        role.format(eid=id, list_id=id, uid=self.uid) and
                        re.match(
                            '^%s$' % policy['resource'].format(
                                eid=id, list_id=id, uid=owner_uid),
                            '%s:%s' % (self.resource, match_id))):
                        actions |= policy['actions']

                    # special-case for person/contact principal:<res>-*
                    elif (policy['principal'] == '%s-*' % membership and
                          role.split('-')[0] == membership and
                          re.match(
                              '^%s$' % policy['resource'].format(
                                  eid=id, list_id=id, uid=owner_uid),
                              '%s:%s' % (self.resource, match_id))):
                        actions |= policy['actions']
        actions -= deny_delete
        return actions if len(actions) else defaults

    def apikey_create(self):
        """Generate an API key - a 41-byte string. First 8 characters (48
        bits) are an access key ID prefix; last 32 characters (192
        bits) are the secret key.

        Returns: tuple
          key ID (str) - public portion of key
          secret (str) - secret portion
          hashvalue (str) - hash value for database
        """
        secret = gen_id(length=35, prefix='')[-32:]
        key_id = gen_id(prefix='')
        return key_id, secret, self.apikey_hash(secret)

    def apikey_verify(self, key_id, secret):
        """Verify an API key

        Args:
          key_id (str): the public key_id at time of generation
          secret (str): the unhashed secret

        Returns: tuple
          uid (str): User ID if valid
          scopes (list): list of scope IDs
        """
        try:
            record = g.db.query(self.models.APIkey).filter_by(
                prefix=key_id, hashvalue=self.apikey_hash(secret),
                status='active').one()
            if not record.last_used or (
                    record.last_used + timedelta(hours=6) < utcnow()
                    and (not record.expires or record.expires < utcnow())):
                record.last_used = utcnow()
                g.db.commit()
        except NoResultFound:
            logging.info(dict(action='api_key', key_id=key_id,
                              message='not found'))
            return None, None
        except Exception as ex:
            logging.error(dict(action='api_key', message=str(ex)))
            return None, None
        if record.expires and record.expires < utcnow():
            logging.info(dict(action='api_key', key_id=key_id,
                              uid=record.uid, message='expired'))
            return None, None
        return record.uid, record.scopes

    @staticmethod
    def apikey_hash(secret):
        """Generate a hash value from the secret
        Args:
          secret (str): secret key
        """
        return b64encode(
            hashlib.sha256(secret.encode()).digest()).decode('utf8')

    @staticmethod
    def _parse_id(role, resource):
        """Given role <res>-<id>-<level>
        Returns id if resource matches, otherwise None

        Args:
          role (str): assigned role
          resource (str): resource type
        """
        x = role.split('-')
        if x and x[0] == resource:
            return '-'.join(x[1:-1])
