"""db_schema.py

Database schema update and seed functions - populate a new db with minimum data

created 31-mar-2019 by richb@instantlinux.net
"""

import logging
import os
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import exc

from apicrud.database import alembic_migrate, get_session, seed_new_db
from models import AlembicVersion


def update(db_engine, models, migrate=False, schema_maxtime=0,
           script_location=os.path.join(os.path.abspath(
               os.path.dirname(__file__)), 'alembic')):
    """Run alembic migrations for updating schema

    Must be called with mutex for duration of update to prevent race
    conditions; begin_transaction() does not ensure mutual exclusion.

    Args:
      db_engine (obj): connection to database
      models (obj): models to generate or update
      migrate (bool): perform migrations only if True
      schema_maxtime (int): maximum seconds to wait for mutex
      script_location (str): path for alembic scripts
    """
    db_session = get_session(scoped=True)
    try:
        version = db_session.query(AlembicVersion).one().version_num
    except (exc.NoResultFound, OperationalError, ProgrammingError) as ex:
        logging.warning('DB schema does not yet exist: %s' % str(ex))
        version = None
    db_session.close()
    alembic_migrate(models, version, script_location, migrate=migrate,
                    schema_maxtime=schema_maxtime, seed_func=seed_new_db)
