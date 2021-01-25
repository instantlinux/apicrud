from flask import g
import logging
from sqlalchemy.orm.exc import NoResultFound

from apicrud import AccountSettings, BasicCRUD
from models import Account


class SettingsController(BasicCRUD):
    def __init__(self):
        super().__init__(resource='settings')

    def update(id, body):
        retval = super(SettingsController, SettingsController).update(
            id, body)
        # Clear cached value for global admin
        if retval[1] == 200:
            account_id = None
            try:
                account_id = g.db.query(Account).filter_by(
                    name='admin').one().id
            except NoResultFound:
                logging.warning('action=update message="Missing admin"')
            AccountSettings(account_id).uncache()
        return retval
