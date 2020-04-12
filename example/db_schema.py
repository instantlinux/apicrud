"""db_schema.py

Database schema update and seed functions - populate a new db with minimum data

created 31-mar-2019 by richb@instantlinux.net
"""

import alembic.config
import alembic.script
from alembic.runtime.environment import EnvironmentContext
import logging
import os
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import exc
from sqlalchemy.sql import select, func
import time

from example import constants
from apicrud.database import Base, get_session, spatialite_loaded
from .models import Account, AlembicVersion, Category, Contact, Location, \
    Person, Settings, TZname


def update(db_engine, models, migrate=False, schema_maxtime=0):
    """Run alembic migrations for updating schema

    Must be called with mutex for duration of update to prevent race
    conditions; begin_transaction() does not ensure mutual exclusion.

    params:
      models - models to generate or update
      migrate - perform migrations only if True
      schema_maxtime - maximum seconds to wait for mutex
    """
    db_session = get_session(scoped=True)
    try:
        version = db_session.query(AlembicVersion).one().version_num
    except (exc.NoResultFound, OperationalError, ProgrammingError) as ex:
        logging.warning('DB schema does not yet exist: %s' % str(ex))
        version = None
    cfg = alembic.config.Config()
    cfg.set_main_option('script_location', os.path.join(
        os.path.abspath(os.path.dirname(__file__)), 'alembic'))
    script = alembic.script.ScriptDirectory.from_config(cfg)
    env = EnvironmentContext(cfg, script)
    if (version == script.get_heads()[0]):
        logging.info('action=schema_update version=%s is current' %
                     version)
    elif migrate:
        def _do_upgrade(revision, context):
            return script._upgrade_revs(script.get_heads(), revision)

        conn = db_engine.connect()
        if db_engine.dialect.name == 'sqlite' and spatialite_loaded:
            conn.execute(select([func.InitSpatialMetaData(1)]))
        env.configure(connection=conn, target_metadata=Base.metadata,
                      fn=_do_upgrade)
        with env.begin_transaction():
            env.run_migrations()
        logging.info('action=schema_update finished migration, '
                     'version=%s' % script.get_heads()[0])
    else:
        # Not migrating: must wait
        wait_time = schema_maxtime
        while version != script.get_heads()[0] and wait_time:
            time.sleep(5)
            wait_time -= 5
    if version is None:
        _seed_new_db(db_session)
    db_session.close()


def _seed_new_db(db_session):
    """ Seed a new db with admin account
    """

    if db_session.bind.dialect.name == 'sqlite':
        db_session.execute('pragma foreign_keys=off')
    else:
        db_session.execute('SET FOREIGN_KEY_CHECKS=0;')
    cat_id, account_id, uid = (
        constants.DEFAULT_CAT_ID, 'x-54320001', 'x-23450001')
    record = Category(id=cat_id, uid=uid, name='default')
    db_session.add(record)
    record = Person(id=uid, name='Example User',
                    identity='example@instantlinux.net', privacy='public',
                    status='active')
    db_session.add(record)
    record = Contact(id='x-4566a239', uid=uid,
                     type='email', info='example@instantlinux.net',
                     muted=True, privacy='public', status='active')
    db_session.add(record)
    record = Account(id=account_id, name='admin', is_admin=True,
                     uid=uid, status='active', settings_id='x-75023275',
                     password_must_change=False,
                     password=constants.LOGIN_ADMIN_DEFAULTPW)
    db_session.add(record)
    record = Settings(id='x-75023275',
                      administrator_id='x-23450001', tz_id=598,
                      default_cat_id=cat_id, name='global',
                      smtp_smarthost='smtp.ci.net', country='US',
                      lang='en_US', url='http://elbrus.ci.net:3000')
    db_session.add(record)
    record = Location(id='x-67673434', city='San Francisco',
                      geolat=37.756503 * 1e7, geolong=-122.425671 * 1e7,
                      address='800 Dolores St.', state='CA',
                      country='US', neighborhood='Mission District',
                      uid=uid, category_id=cat_id, status='active')
    db_session.add(record)
    record = TZname(id=308, name='Asia/Seoul')
    db_session.add(record)
    record = TZname(id=309, name='Asia/Shanghai')
    db_session.add(record)
    record = TZname(id=315, name='Asia/Tehran')
    db_session.add(record)
    record = TZname(id=319, name='Asia/Tokyo')
    db_session.add(record)
    record = TZname(id=460, name='Europe/Paris')
    db_session.add(record)
    record = TZname(id=457, name='Europe/Moscow')
    db_session.add(record)
    record = TZname(id=464, name='Europe/Rome')
    db_session.add(record)
    record = TZname(id=591, name='US/Central')
    db_session.add(record)
    record = TZname(id=593, name='US/Eastern')
    db_session.add(record)
    record = TZname(id=597, name='US/Mountain')
    db_session.add(record)
    record = TZname(id=598, name='US/Pacific')
    db_session.add(record)
    record = TZname(id=601, name='UTC')
    db_session.add(record)
    if db_session.bind.dialect.name == 'sqlite':
        db_session.execute('pragma foreign_keys=on')
    else:
        db_session.execute('SET FOREIGN_KEY_CHECKS=1;')
    db_session.commit()
