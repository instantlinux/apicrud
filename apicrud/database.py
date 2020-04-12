"""database.py

Database session management and schema update

created 31-mar-2019 by richb@instantlinux.net
"""

from flask import _app_ctx_stack
import logging
import os.path
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.event import listen
from sqlalchemy.ext.declarative import declarative_base

from . import constants
from .session_manager import Mutex

Base = declarative_base()
db_engine = None
Session = None
spatialite_loaded = False


def get_session(scopefunc=None, scoped=True, db_url=None, engine=None):
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


def initialize_db(models, db_url=None, engine=None, redis_conn=None,
                  redis_host=None, migrate=False, geo_support=False,
                  connection_timeout=0, schema_update=None, schema_maxtime=60):
    _init_db(db_url=db_url, engine=engine, geo_support=geo_support,
             connection_timeout=connection_timeout)
    if migrate:
        with Mutex('alembic', redis_host=redis_host,
                   ttl=schema_maxtime, redis_conn=redis_conn):
            schema_update(db_engine, models, migrate=True,
                          schema_maxtime=schema_maxtime)
    else:
        # just wait for schema update
        schema_update(db_engine, models)


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
    Base.metadata.create_all(bind=db_engine)
    return db_engine


def _load_spatialite(dbapi_conn, connection_record):
    global spatialite_loaded
    for lib in constants.LIB_MOD_SPATIALITE:
        if os.path.exists(lib):
            dbapi_conn.enable_load_extension(True)
            dbapi_conn.load_extension(lib)
            logging.info('action=load_spatialite message=geo_support_added')
            spatialite_loaded = True
            return
