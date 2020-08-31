"""database.py

Database session management and schema update

created 31-mar-2019 by richb@instantlinux.net
"""

import alembic.config
import alembic.script
from alembic.runtime.environment import EnvironmentContext
from flask import _app_ctx_stack
import logging
import os.path
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.event import listen
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import select, func
import time
import yaml

from .const import Constants
from .session_manager import Mutex
from .service_config import ServiceConfig

Base = declarative_base()
db_engine = None
Session = None
spatialite_loaded = False


def get_session(scopefunc=None, scoped=True, db_url=None, engine=None):
    """open a db session scoped to flask context or celery thread

    Args:
      scopefunc (function): function which returns a unique thread ID
      scoped (bool): whether to use scoped session management
      db_url (str): URL of database
      engine (obj): override engine object (for unit tests)
    Returns:
      obj: session
    """

    global db_engine
    if not engine:
        # This is where init_db is invoked under celery
        engine = db_engine or _init_db(db_url=db_url)
    if scoped:
        global Session
        if scopefunc is None:
            scopefunc = _app_ctx_stack.__ident_func__
        Session = scoped_session(sessionmaker(autocommit=False,
                                              autoflush=False,
                                              bind=engine),
                                 scopefunc=scopefunc)
        return Session
    else:
        Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        return Session


def initialize_db(db_url=None, engine=None, redis_conn=None):
    """initialize database connectivity

    Args:
      db_url (str): URL of database
      engine (obj): override engine object (for unit tests)
      redis_conn (obj): redis connection object override (for unit tests)
    """

    config = ServiceConfig().config
    models = ServiceConfig().models
    _init_db(db_url=db_url, geo_support=config.DB_GEO_SUPPORT,
             engine=engine, connection_timeout=config.DB_CONNECTION_TIMEOUT)
    if config.DB_MIGRATE_ENABLE:
        with Mutex('alembic', redis_host=config.REDIS_HOST,
                   ttl=config.DB_SCHEMA_MAXTIME, redis_conn=redis_conn):
            schema_update(db_engine, models)
    else:
        # just wait for schema update
        schema_update(db_engine, models)


def alembic_migrate(models, version, script_location, migrate=False,
                    db_session=None, schema_maxtime=0, seed_func=None):
    """run schema migrations

    Args:
      models (obj): the models file object
      version (str): schema version expected after migration
      script_location (str): relative path name of alembic's env.py
      migrate (bool): whether to run alembic migrations
      db_session (obj): existing db session
      schema_maxtime (int): how long to wait for migration
      seed_func (function): function to seed initial records in blank db
    """

    cfg = alembic.config.Config()
    cfg.set_main_option('script_location', script_location)
    script = alembic.script.ScriptDirectory.from_config(cfg)
    env = EnvironmentContext(cfg, script)
    if (version == script.get_heads()[0]):
        logging.info('action=schema_update version=%s is current' %
                     version)
    elif migrate:
        def _do_upgrade(revision, context):
            return script._upgrade_revs(script.get_heads(), revision)

        while schema_maxtime > 0:
            try:
                conn = db_engine.connect()
                break
            except OperationalError as ex:
                logging.info('action=alembic_migrate status=waiting message=%s'
                             % str(ex))
            schema_maxtime -= 10
            time.sleep(10)
        if db_engine.dialect.name == 'sqlite' and spatialite_loaded:
            conn.execute(select([func.InitSpatialMetaData(1)]))
        env.configure(connection=conn, target_metadata=Base.metadata,
                      verbose=True, fn=_do_upgrade)
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
    if version is None and seed_func:
        if not db_session:
            db_session = get_session(scoped=True)
        seed_func(db_session)
        db_session.close()


def schema_update(db_engine, models):
    """Run alembic migrations for updating schema

    Must be called with mutex for duration of update to prevent race
    conditions; begin_transaction() does not ensure mutual exclusion.

    Args:
      db_engine (obj): connection to database
      models (obj): models to generate or update
    """
    db_session = get_session(scoped=True)
    config = ServiceConfig().config
    script_location = config.DB_MIGRATIONS
    try:
        version = db_session.query(models.AlembicVersion).one().version_num
    except (NoResultFound, OperationalError, ProgrammingError) as ex:
        logging.warning('DB schema does not yet exist: %s' % str(ex))
        version = None
    db_session.close()
    if config.DB_SCHEMA_MAXTIME == 0:
        logging.info('found schema version=%s, skipping update' % version)
    else:
        alembic_migrate(models, version, script_location,
                        migrate=config.DB_MIGRATE_ENABLE,
                        schema_maxtime=config.DB_SCHEMA_MAXTIME,
                        seed_func=seed_new_db)


def seed_new_db(db_session, tz_model=None):
    """Seed a new db with admin account and related records. Reads
    records defined in a file db_seed.yaml (or as otherwise specified
    in the main config.yaml) and places them in the database.

    Args:
      db_session (obj): existing db session
      tz_model (obj): timezone model [default models.Tz]
    """

    if db_session.bind.dialect.name == 'sqlite':
        cmd = 'pragma foreign_keys'
    else:
        cmd = 'SET FOREIGN_KEY_CHECKS'
    db_session.execute('%s=off' % cmd)
    with open(ServiceConfig().config.DB_SEED_FILE, 'rt', encoding='utf8') as f:
        records = yaml.safe_load(f)
    models = ServiceConfig().models
    if not tz_model:
        tz_model = models.Tz
    for resource, record in records.items():
        if 'geolat' in record:
            # Store lat/long as fixed-precision integers
            record['geolat'] *= 1e7
            record['geolong'] *= 1e7
        db_session.add(getattr(models, resource.capitalize())(**record))
    _seed_tz_table(db_session, tz_model)
    db_session.execute('%s=on' % cmd)
    db_session.commit()


def _init_db(db_url=None, engine=None, connection_timeout=0,
             geo_support=True):
    global db_engine
    if not db_engine:
        try:
            db_engine = engine or create_engine(
                db_url, pool_pre_ping=True,
                pool_recycle=connection_timeout)
        except Exception as ex:
            logging.error('action=init_db status=error message=%s' % str(ex))
            return None
    if db_engine.url.drivername == 'sqlite':
        db_engine.execute('pragma foreign_keys=on')
        if geo_support:
            listen(db_engine, 'connect', _load_spatialite)
    db = get_session(scoped=True)
    if hasattr(db, 'query_property'):
        Base.query = db.query_property()
        db.remove()
    connection_timeout = 20
    while connection_timeout > 0:
        try:
            Base.metadata.create_all(bind=db_engine)
            break
        except OperationalError as ex:
            logging.info('action=init_db status=waiting message=%s' % str(ex))
        connection_timeout -= 10
        time.sleep(10)
    return db_engine


def _load_spatialite(dbapi_conn, connection_record):
    global spatialite_loaded
    for lib in Constants.LIB_MOD_SPATIALITE:
        if os.path.exists(lib):
            dbapi_conn.enable_load_extension(True)
            dbapi_conn.load_extension(lib)
            logging.info('action=load_spatialite message=geo_support_added')
            spatialite_loaded = True
            return


def _seed_tz_table(db_session, model):
    """Add standard timezone names to the timezone table.
    Most of the ID values are from:
      https://code2care.org/pages/java-timezone-list-utc-gmt-offset
    ID values don't really matter, but they should remain as
    unchanging and universal as possible. This list is curated to
    be short enough for a user to quickly select from a dropdown,
    but long enough to represent almost all of the world's timezones.

    Note that additions can be made to the db_seed.yaml (resource
    type 'tz').

    Args:
        db_session (obj): an open session
        model (obj): the TZ table model definition
    """
    db_session.add(model(id=14, name='Africa/Cairo'))
    db_session.add(model(id=15, name='Africa/Casablanca'))
    db_session.add(model(id=26, name='Africa/Johannesburg'))
    db_session.add(model(id=32, name='Africa/Lagos'))
    db_session.add(model(id=44, name='Africa/Nairobi'))
    db_session.add(model(id=247, name='Asia/Bangkok'))
    db_session.add(model(id=259, name='Asia/Damascus'))
    db_session.add(model(id=262, name='Asia/Dubai'))
    db_session.add(model(id=269, name='Asia/Hong_Kong'))
    db_session.add(model(id=272, name='Asia/Istanbul'))
    db_session.add(model(id=273, name='Asia/Jakarta'))
    db_session.add(model(id=275, name='Asia/Jerusalem'))
    db_session.add(model(id=276, name='Asia/Kabul'))
    db_session.add(model(id=278, name='Asia/Karachi'))
    db_session.add(model(id=287, name='Asia/Kuwait'))
    db_session.add(model(id=292, name='Asia/Manila'))
    db_session.add(model(id=306, name='Asia/Riyadh'))
    db_session.add(model(id=307, name='Asia/Saigon'))
    db_session.add(model(id=308, name='Asia/Seoul'))
    db_session.add(model(id=309, name='Asia/Shanghai'))
    db_session.add(model(id=314, name='Asia/Taipei'))
    db_session.add(model(id=315, name='Asia/Tehran'))
    db_session.add(model(id=319, name='Asia/Tokyo'))
    db_session.add(model(id=334, name='Atlantic/Azores'))
    db_session.add(model(id=360, name='Australia/North'))
    db_session.add(model(id=362, name='Australia/Queensland'))
    db_session.add(model(id=363, name='Australia/South'))
    db_session.add(model(id=364, name='Australia/Sydney'))
    db_session.add(model(id=365, name='Australia/Tasmania'))
    db_session.add(model(id=366, name='Australia/Victoria'))
    db_session.add(model(id=367, name='Australia/West'))
    db_session.add(model(id=370, name='Brazil/DeNoronha'))
    db_session.add(model(id=371, name='Brazil/East'))
    db_session.add(model(id=372, name='Brazil/West'))
    db_session.add(model(id=375, name='Canada/Atlantic'))
    db_session.add(model(id=376, name='Canada/Central'))
    db_session.add(model(id=377, name='Canada/Eastern'))
    db_session.add(model(id=378, name='Canada/Mountain'))
    db_session.add(model(id=379, name='Canada/Newfoundland'))
    db_session.add(model(id=380, name='Canada/Pacific'))
    db_session.add(model(id=383, name='Chile/Continental'))
    db_session.add(model(id=428, name='Europe/Athens'))
    db_session.add(model(id=444, name='Europe/Istanbul'))
    db_session.add(model(id=457, name='Europe/Moscow'))
    db_session.add(model(id=460, name='Europe/Paris'))
    db_session.add(model(id=464, name='Europe/Rome'))
    db_session.add(model(id=520, name='PRC'))
    db_session.add(model(id=586, name='US/Arizona'))
    db_session.add(model(id=590, name='US/Hawaii'))
    db_session.add(model(id=591, name='US/Central'))
    db_session.add(model(id=593, name='US/Eastern'))
    db_session.add(model(id=596, name='US/Samoa'))
    db_session.add(model(id=597, name='US/Mountain'))
    db_session.add(model(id=598, name='US/Pacific'))
    db_session.add(model(id=601, name='UTC'))
    db_session.add(model(id=619, name='IST'))
