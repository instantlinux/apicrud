"""local_func

created 26-mar-2020 by richb@instantlinux.net
"""
from flask import g
from flask_babel import _
import logging
from passlib.hash import sha256_crypt
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy_utils.types.encrypted.padding import InvalidPaddingError

from .. import ServiceConfig
from ..database import db_abort


def login(username, password):
    """Login using credentials stored in local database.  If
    successful, this passes a sqlalchemy account record back for
    further processing by SessionAuth.login_accepted.

    Args:
      username (str): the username or email identity
      password (str): password

    Returns:
      tuple: dict with error message, http status (200 if OK), account object
    """
    models = ServiceConfig().models
    try:
        if '@' in username:
            account = g.db.query(models.Account).join(
                models.Person).filter(
                    models.Person.identity == username,
                    models.Account.status == 'active').one()
            username = account.name
        else:
            account = g.db.query(models.Account).filter_by(
                name=username, status='active').one()
    except InvalidPaddingError:
        logging.error('action=login message="invalid DB_AES_SECRET"')
        return dict(message=_(u'DB operational error')), 503, None
    except (NoResultFound, TypeError):
        return dict(username=username, message=_(u'not valid')), 403, None
    except OperationalError as ex:
        return db_abort(str(ex), action='login')

    if account.password == '':
        logging.error("username=%s, message='no password'" % username)
        return dict(username=username, message=_(u'no password')), 403, None
    elif not password or not sha256_crypt.verify(password, account.password):
        logging.info(dict(action='login', method='local',
                          username=username, credential='invalid'))
        g.db.commit()
        return dict(username=username, message=_(u'not valid')), 403, None

    return {}, 200, account
