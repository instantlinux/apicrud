"""grant controller

created 27-may-2019 by richb@instantlinux.net
"""

from flask import g
import json
import logging

from apicrud.access import AccessControl
from apicrud.account_settings import AccountSettings
from apicrud.basic_crud import BasicCRUD
from apicrud.grants import Grants
from apicrud.service_config import ServiceConfig


class GrantController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='grant')

    @staticmethod
    def create(body):
        Grants().uncache(body.get('uid'))
        return super(GrantController, GrantController).create(body)

    @staticmethod
    def update(id, body):
        """If the id has a hybrid uid:grant syntax, invoke create
        instead; otherwise it's a standard update

        Args:
            id (str): Database or hybrid grant ID
            body (dict): resource fields as defined by openapi.yaml schema
        """
        Grants().uncache(body.get('uid'))
        if ':' in id:
            body['uid'] = id.split(':')[0]
            body.pop('id', None)
            return super(GrantController, GrantController).create(body)
        return super(GrantController, GrantController).update(id, body)

    @staticmethod
    def get(id):
        """If the id is found in database, perform the standard CRUD
        get(). Otherwise, look for a hybrid id in form uid:grant and
        return the cached Grant value.

        Args:
            id (str): Database or hybrid grant ID
        """
        retval = super(GrantController, GrantController).get(id)
        if retval[1] == 200 or ':' not in id:
            return retval
        logging.info(retval)
        models = ServiceConfig().models
        acc = AccessControl(model=models.Grant)
        uid, grantname = id.split(':')
        admin_id = AccountSettings(
            account_id=acc.account_id, db_session=g.db).get.administrator_id
        rbac = ''.join(sorted(list(acc.rbac_permissions(owner_uid=admin_id))))
        if 'r' not in rbac:
            return dict('access denied'), 403
        return dict(id=id,  uid=uid, name=grantname, value=str(Grants(
            ).get(grantname, uid=uid)), rbac=rbac, status='active'), 200

    @staticmethod
    def find(**kwargs):
        retval = super(GrantController, GrantController).find(**kwargs)
        filter = json.loads(kwargs.get('filter', '{}'))
        config = ServiceConfig().config
        models = ServiceConfig().models
        acc = AccessControl(model=models.Grant)
        uid = filter.get('uid') or acc.uid
        admin_id = AccountSettings(
            account_id=acc.account_id, db_session=g.db).get.administrator_id
        rbac = ''.join(sorted(list(acc.rbac_permissions(owner_uid=admin_id))))
        result = []
        for key, val in config.DEFAULT_GRANTS.items():
            if 'name' in filter and key != filter.get('name'):
                continue
            for row in retval[0]['items']:
                if row['name'] == key:
                    result.append(row)
                    break
            else:
                result.append(dict(id='%s:%s' % (uid, key), uid=uid,
                                   name=key, value=str(val), rbac=rbac,
                                   status='active'))
        return dict(items=result, count=len(result)), retval[1]
