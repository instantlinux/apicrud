from __future__ import with_statement
from alembic import context
import os
from sqlalchemy import engine_from_config, pool
from logging.config import fileConfig

from apicrud.models import Base

import sys
src_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        '..'
    ))
sys.path.append(src_path)

# for autogenerate, update models.py and:
#  cd example
#  DB_URL=mysql+pymysql://$user:$pw@db00/example_local \
#    PYTHONPATH=.. alembic revision --autogenerate -m "comment"
#
# Then run once with compare_type=True to check for omitted
# minor changes
#
# Lots of things need editing after autogenerate:
#   - Replace None with a '<table>_fkN' for each create_foreign_key
#   - If renaming column, collapse add_column/drop into alter_column
#   - If renaming column, create second 'with op.batch_alter_table'
#       codeblock for create_foreign_key
#   - Use the compare_type feature on initial pass to detect any
#       column updates (other than boolean, kinda buggy)
#   - Comment out drop_constraint lines (for sqlite)
#   - and probably more, autogenerate is a steaming pile of donkey shit,
#       but slightly more useful than not using it

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
config.set_main_option('sqlalchemy.url', os.environ.get(
    'DB_URL', 'sqlite:////tmp/apicrud.db'))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def include_object(
        object, name, type_, reflected, compare_to, schema='apicrud'):
    if type_ == 'table' and object.schema != schema:
        return False
    else:
        return True


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    raise AssertionError('Function not supported')
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            # uncomment to pick up column-type changes
            # compare_type=True,
            render_as_batch=True,
            connection=connection,
            include_object=include_object,
            target_metadata=target_metadata,
            version_table='alembic_version_apicrud'
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
