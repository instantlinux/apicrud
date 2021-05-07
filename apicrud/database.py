"""database.py

Database session management and schema update

created 31-mar-2019 by richb@instantlinux.net
"""

import alembic.config
import alembic.script
from alembic.runtime.environment import EnvironmentContext
from flask import _app_ctx_stack, g
from flask_babel import _
import logging
import os.path
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.event import listen
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import select, func
import sys
import time
import yaml

from .const import Constants
from .session_manager import Mutex
from .service_config import ServiceConfig
from .utils import utcnow

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
        if engine.url.drivername == 'sqlite':
            Session.execute('PRAGMA foreign_keys=on')
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

    Returns:
      bool: True if successful
    """
    config = ServiceConfig().config
    models = ServiceConfig().models
    _init_db(db_url=db_url, geo_support=config.DB_GEO_SUPPORT,
             engine=engine, connection_timeout=config.DB_CONNECTION_TIMEOUT)
    if config.DB_MIGRATE_ENABLE:
        try:
            with Mutex('alembic', redis_host=config.REDIS_HOST,
                       ttl=config.DB_SCHEMA_MAXTIME, redis_conn=redis_conn):
                schema_update(db_engine, models)
        except TimeoutError:
            logging.error(dict(action='init_db', message='mutex timeout'))
            return False
    else:
        # just wait for schema update
        schema_update(db_engine, models)
    return True


def db_abort(error, rollback=False, **kwargs):
    """Helper for logging exceptions
    Args:
      error (str): exception string for log
      rollback (bool): whether to roll back
      kwargs: any other values to log

    Returns:
      tuple: dict with generic message, status 500
    """
    msg = _(u'DB operational error')
    logging.error(dict(message=msg, error=error, **kwargs))
    g.db.rollback()
    return dict(message=msg), 500


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

    start = utcnow().timestamp()
    cfg = alembic.config.Config()
    cfg.set_main_option('script_location', script_location)
    script = alembic.script.ScriptDirectory.from_config(cfg)
    env = EnvironmentContext(cfg, script)
    logmsg = dict(action='schema_update', version=version)
    if (version == script.get_heads()[0]):
        logging.info(dict(message='is current', duration='%.3f' %
                          (utcnow().timestamp() - start), **logmsg))
    elif migrate:
        def _do_upgrade(revision, context):
            return script._upgrade_revs(script.get_heads(), revision)

        conn = None
        while schema_maxtime > 0:
            try:
                conn = db_engine.connect()
                break
            except OperationalError as ex:
                logging.info('action=alembic_migrate status=waiting message=%s'
                             % str(ex))
            schema_maxtime -= 10
            time.sleep(10)
        if not conn:
            logging.error('action=alembic_migrate status=timeout')
            sys.exit(1)
        if db_engine.dialect.name == 'sqlite' and spatialite_loaded:
            conn.execute(select([func.InitSpatialMetaData(1)]))
        env.configure(connection=conn, target_metadata=Base.metadata,
                      verbose=True, fn=_do_upgrade)
        with env.begin_transaction():
            env.run_migrations()
        logging.info(dict(message='finished migration', duration='%0.3f' %
                          (utcnow().timestamp() - start), **logmsg))
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


def seed_new_db(db_session):
    """Seed a new db with admin account and related records. Reads
    records defined in a file db_seed.yaml (or as otherwise specified
    in the main config.yaml) and places them in the database. Timezone
    name records are loaded from this source directory's timezones.yaml
    unless at least one tz record is provided in db_seed.yaml.

    Args:
      db_session (obj): existing db session
    """

    if db_session.bind.dialect.name == 'sqlite':
        cmd = 'pragma foreign_keys'
    else:
        cmd = 'SET FOREIGN_KEY_CHECKS'
    db_session.execute('%s=off' % cmd)
    with open(ServiceConfig().config.DB_SEED_FILE, 'rt', encoding='utf8') as f:
        records = yaml.safe_load(f)
    if 'tz' not in records:
        with open(os.path.join(os.path.dirname(
                __file__), 'timezones.yaml'), 'rt', encoding='utf8') as f:
            records['tz'] = yaml.safe_load(f)['tz']
    models = ServiceConfig().models
    for resource, records in records.items():
        if resource == '_constants':
            continue
        for record in records:
            if 'geolat' in record:
                # Store lat/long as fixed-precision integers
                record['geolat'] *= 1e7
                record['geolong'] *= 1e7
            db_session.add(getattr(models, resource.capitalize())(**record))
    db_session.commit()
    db_session.execute('%s=on' % cmd)


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
        db_engine.execute('PRAGMA foreign_keys=on')
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
