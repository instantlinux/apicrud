"""access.py

Access control

  Definitions:
    principal: a user or role
    membership: parent resource type for privacy sharing
    model: database model name (e.g. Person)
    resource: resource type (e.g. person)
    rbac: role-based access control (defined in rbac.yaml)
    role: a group name (e.g. admin or list-<id>-<level>)
    privacy: sharing options as defined in rbac.yaml (e.g.
      secret [default], public, invitee, member, manager)
    actions: crudlghij (create, read, update, del, list, guest/member,
      host/manager, invitee, join)

  In rbac.yaml, define the RBAC policies for each principal/resource
  combination. That file will be parsed into a singleton variable upon initial
  startup.  This implementation implements RBAC similar to that of
  kubernetes or AWS IAM, with the added capability of a simple privacy
  permission within each object (database record) which creates an implied
  ACL for read-only access by members of the object's group.

  Group names currently used are:
    admin
    user
    pending
    person
    <resource>-<id>-<privacy>
  These are defined in session_auth.py's account_login() method.

created 20-may-2019 by richb@instantlinux.net
refactored 6-mar-2020
"""

from datetime import datetime
from flask import g, request
import logging
import re
from sqlalchemy import or_
from sqlalchemy.orm.exc import NoResultFound
import yaml

LEVELS = {}
POLICIES = {}
PRIV_RES = {}


class AccessControl(object):
    def __init__(self, policy_file=None, models=None, model=None):
        if POLICIES and request:
            self.policies = POLICIES['policies']
            self.privacy_levels = LEVELS['levels']
            self.private_res = PRIV_RES['private_res']
            creds = request.authorization
            self.model = model
            self.models = models
            self.resource = model.__name__.lower() if model else None
            self.auth = None
            if creds:
                try:
                    self.auth = g.session.get(
                        creds.username, creds.password, arg='auth').split(':')
                except AttributeError:
                    pass
            self.primary_res = self.private_res[0]['resource']
            self.auth_ids = {self.primary_res: []}
            if self.auth:
                for role in self.auth:
                    ev = self._parse_id(role, self.primary_res)
                    if ev:
                        self.auth_ids[self.primary_res].append(ev)
                uid = self.uid = creds.username
                self.account_id = g.session.get(uid, creds.password, 'acc')
                self.identity = g.session.get(uid, creds.password, 'identity')
            else:
                logging.warning('no-auth resource=%s attempted' %
                                self.resource)
                self.auth = self.uid = self.account_id = self.identity = None

    def load_rbac(self, filename):
        """ Read RBAC default policies from rbac.yaml, process any
        string substitutions, and convert * for re.match()
        """

        with open(filename, 'r') as f:
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
                self.private_res = rbac['private_resources']
                LEVELS['levels'] = self.privacy_levels
                POLICIES['policies'] = self.policies
                PRIV_RES['private_res'] = self.private_res

    def with_permission(self, access, query=None, new_uid=None,
                        membership=None, id=None):
        """Pass in at least one of the query/uid/eid params

        params:
          access (str) - one of lrwcd (list, read, write, create, delete)
          query (obj) - a resource query by id in SQLalchemy
          new_uid (str) - user id of a new record
          membership - resource type which defines membership privacy
          id (str) - resource ID
        """
        rbac = self.rbac_permissions(query=query, owner_uid=new_uid,
                                     membership=membership, id=id)
        if access in rbac:
            return True
        else:
            duration = (datetime.utcnow().timestamp() -
                        g.request_start_time.timestamp())
            logging.info(dict(
                action='with_permission', message='access denied',
                resource=self.resource, uid=self.uid, ident=self.identity,
                access=access, rbac=rbac, duration='%.3f' % duration))
        return False

    def with_filter(self, query, access='r'):
        """Apply RBAC and privacy to a query

        params:
          query (obj) - a resource query in SQLalchemy
          access (str) - one of lrwcd (list, read, write, create, delete)

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

        params:
          query - an existing record (takes precedence over owner_uid)
          owner_uid - owner-uid of a record
          membership - resource type which defines membership privacy
          id - the resource ID if membership is set
        returns: set of actions available to principal
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
                owner_uid = query.one().owner.referrer_id
            # TODO redesign fragile dependency on primary contact
            try:
                g.db.query(self.models.Person).filter_by(
                    identity=query.one().info).one()
                deny_delete = set('d')
            except NoResultFound:
                pass

        actions, defaults = (set(), set())
        if privacy == 'public' or (
                id and '%s-%s-%s' % (membership, id, privacy) in self.auth):
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

    @staticmethod
    def _parse_id(role, resource):
        """Given role <res>-<id>-<level>
        Returns id if resource matches, otherwise None
        """
        x = role.split('-')
        if x and x[0] == resource:
            return '-'.join(x[1:-1])
