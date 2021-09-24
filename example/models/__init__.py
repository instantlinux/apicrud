"""models

Database model definitions for SQLalchemy

created 26-mar-2019 by richb@instantlinux.net
"""
from sqlalchemy import Column, String

from apicrud.models.base import Base
from apicrud.models.api import *  # noqa

from .api import *  # noqa


class AlembicVersionMain(Base):
    __tablename__ = 'alembic_version_main'
    version_num = Column(String(32), primary_key=True, nullable=False)
