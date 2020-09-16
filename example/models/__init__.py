"""models

Database model definitions for SQLalchemy

created 26-mar-2019 by richb@instantlinux.net
"""
from sqlalchemy import Column, String

from .base import Base
from .api import *  # noqa


class AlembicVersion(Base):
    __tablename__ = 'alembic_version'
    version_num = Column(String(32), primary_key=True, nullable=False)
