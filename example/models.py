"""example-app models

Database model definitions for SQLalchemy

created 26-mar-2019 by richb@instantlinux.net

license: lgpl-2.1
"""

# coding: utf-8

# from geoalchemy2 import Geometry
from sqlalchemy import BOOLEAN, Column, Enum, ForeignKey, INTEGER, String, \
     TEXT, TIMESTAMP, Unicode, UniqueConstraint
from sqlalchemy import func
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy_utils import EncryptedType
from sqlalchemy_utils.types.encrypted.encrypted_type import AesEngine

import config
import constants

Base = declarative_base()
aes_secret = config.DB_AES_SECRET


class Account(Base):
    __tablename__ = 'accounts'
    __table_args__ = (
        UniqueConstraint(u'id', u'uid', name='uniq_account_user'),
    )

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(32), nullable=False, unique=True)
    uid = Column(ForeignKey(u'people.id', ondelete='CASCADE'), nullable=False,
                 unique=True)
    password = Column(EncryptedType(Unicode, aes_secret, AesEngine, 'pkcs5'),
                      nullable=False)
    password_must_change = Column(BOOLEAN, nullable=False,
                                  server_default="False")
    totp_secret = Column(EncryptedType(Unicode, aes_secret, AesEngine,
                                       'pkcs5'))
    is_admin = Column(BOOLEAN, nullable=False, server_default="False")
    settings_id = Column(ForeignKey(u'settings.id'), nullable=False)
    last_login = Column(TIMESTAMP)
    invalid_attempts = Column(INTEGER, nullable=False, server_default="0")
    last_invalid_attempt = Column(TIMESTAMP)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum(u'active', u'disabled'), nullable=False)

    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'account_uid', cascade='all, delete-orphan'))
    settings = relationship('Settings')

    def as_dict(self):
        return {col.name: getattr(self, col.name)
                for col in self.__table__.columns
                if col.name not in [
                        'password', 'totp_secret', 'invalid_attempts',
                        'last_invalid_attempt']}


class Category(Base):
    __tablename__ = 'categories'
    __table_args__ = (
        UniqueConstraint(u'name', u'uid', name='uniq_category_owner'),
    )

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(64), nullable=False)
    uid = Column(ForeignKey(u'people.id'), nullable=False)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum('active', u'disabled'), nullable=False,
                    server_default=u'active')

    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'category_uid', cascade='all, delete-orphan'))

    # TODO - dry this out
    def as_dict(self):
        return {col.name: getattr(self, col.name)
                for col in self.__table__.columns}


class Contact(Base):
    __tablename__ = 'contacts'
    __table_args__ = (
        UniqueConstraint(u'info', u'type', name='uniq_info_type'),
    )

    id = Column(String(16), primary_key=True, unique=True)
    label = Column(Enum(u'home', u'mobile', u'other', u'work'),
                   nullable=False, server_default=u'home')
    type = Column(Enum(u'email', u'linkedin', u'location', u'messenger',
                       u'slack', u'sms', u'voice', u'whatsapp'),
                  nullable=False, server_default=u'email')
    carrier = Column(String(16))
    info = Column(String(255))
    muted = Column(BOOLEAN, nullable=False, server_default="False")
    rank = Column(INTEGER, nullable=False, server_default="1")
    uid = Column(ForeignKey(u'people.id', ondelete='CASCADE'), nullable=False,
                 index=True)
    privacy = Column(String(8), nullable=False, server_default=u'member')
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum(u'active', u'unconfirmed', u'disabled'),
                    nullable=False, server_default=u'unconfirmed')

    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'contacts', cascade='all, delete-orphan'))

    def as_dict(self):
        return {col.name: getattr(self, col.name)
                for col in self.__table__.columns}


class Credential(Base):
    __tablename__ = 'credentials'
    __table_args__ = (
        UniqueConstraint(u'name', u'uid', name='uniq_name_uid'),
    )

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(64), nullable=False)
    vendor = Column(String(32), nullable=False)
    # placeholder field TODO make clear how this will be used
    #  probably to delegate to Secrets Manager / KMS
    type = Column(String(16))
    url = Column(String(length=64))
    key = Column(String(length=128))
    secret = Column(EncryptedType(Unicode, aes_secret, AesEngine, 'pkcs5'))
    otherdata = Column(EncryptedType(Unicode, aes_secret, AesEngine, 'pkcs5'))
    expires = Column(TIMESTAMP)
    settings_id = Column(ForeignKey(u'settings.id'), nullable=False)
    uid = Column(ForeignKey(u'people.id', ondelete='CASCADE'), nullable=False)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum(u'active', u'disabled'), nullable=False,
                    server_default=u'active')

    settings = relationship('Settings', foreign_keys=[settings_id])
    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'credential_uid', cascade='all, delete-orphan'))

    def as_dict(self):
        return {col.name: getattr(self, col.name)
                for col in self.__table__.columns}


class DirectMessage(Base):
    __tablename__ = 'directmessages'

    message_id = Column(ForeignKey(u'messages.id', ondelete='CASCADE'),
                        primary_key=True, nullable=False)
    uid = Column(ForeignKey(u'people.id', ondelete='CASCADE'),
                 primary_key=True, nullable=False, index=True)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())

    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'directmessages', cascade='all, delete-orphan'))
    message = relationship('Message', backref=backref(
        'directmessages', cascade='all, delete-orphan'))


class Grant(Base):
    __tablename__ = 'grants'
    __table_args__ = (
        UniqueConstraint(u'name', u'uid', name='uniq_grant_user'),
    )

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(24), nullable=False)
    value = Column(String(64), nullable=False)
    uid = Column(ForeignKey(u'people.id'), nullable=False)
    expires = Column(TIMESTAMP)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum('active', u'disabled'), nullable=False,
                    server_default=u'active')

    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'grant_uid', cascade='all, delete-orphan'))

    def as_dict(self):
        return {col.name: getattr(self, col.name)
                for col in self.__table__.columns}


class List(Base):
    __tablename__ = 'lists'
    __table_args__ = (
        UniqueConstraint(u'name', u'uid', name='uniq_list_owner'),
    )

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(64), nullable=False)
    description = Column(TEXT())
    privacy = Column(String(8), nullable=False, server_default=u'secret')
    category_id = Column(ForeignKey(u'categories.id'), nullable=False)
    uid = Column(ForeignKey(u'people.id', ondelete='CASCADE'), nullable=False)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum('active', u'disabled'), nullable=False)

    members = relationship('Person', secondary='listmembers',
                           backref=backref('people'), order_by='Person.name')
    messages = relationship('Message', secondary='listmessages',
                            backref=backref('lists'),
                            order_by='Message.created')
    category = relationship('Category')
    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'list_uid', cascade='all, delete-orphan'))

    def as_dict(self):
        retval = self.__dict__.copy()
        retval['members'] = [member.id for member in self.members]
        retval.pop('_sa_instance_state', None)
        return retval


# see https://docs.sqlalchemy.org/en/13/orm/extensions/associationproxy.html
class ListMember(Base):
    __tablename__ = 'listmembers'

    uid = Column(ForeignKey(u'people.id', ondelete='CASCADE'),
                 primary_key=True, nullable=False)
    list_id = Column(ForeignKey(u'lists.id', ondelete='CASCADE'),
                     primary_key=True, nullable=False, index=True)
    authorization = Column(String(8), nullable=False,
                           server_default=u'member')
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())

    person = relationship('Person', foreign_keys=[uid], backref=backref(
        'listmembers', cascade='all, delete-orphan'))
    list = relationship('List', backref=backref(
        'listmembers', cascade='all, delete-orphan'))


class ListMessage(Base):
    __tablename__ = 'listmessages'

    message_id = Column(ForeignKey(u'messages.id', ondelete='CASCADE'),
                        primary_key=True, nullable=False)
    list_id = Column(ForeignKey(u'lists.id', ondelete='CASCADE'),
                     primary_key=True, nullable=False, index=True)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())

    message = relationship(
        'Message', foreign_keys=[message_id], backref=backref(
            'listmessages', cascade='all, delete-orphan'))
    list = relationship('List', backref=backref(
        'listmessages', cascade='all, delete-orphan'))


class Location(Base):
    __tablename__ = 'locations'

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(255))
    address = Column(String(255))
    city = Column(String(64), nullable=False)
    state = Column(String(16))
    postalcode = Column(String(12))
    country = Column(String(2), nullable=False,
                     server_default=constants.DEFAULT_COUNTRY)
    # MariaDB is not supported by geoalchemy2, alas
    # geo = Column(Geometry(geometry_type='POINT'))
    # Coordinates are stored as fixed-precision (divide by 1e7)
    geolat = Column(INTEGER)
    geolong = Column(INTEGER)
    neighborhood = Column(String(32))
    privacy = Column(String(8), nullable=False, server_default=u'public')
    uid = Column(ForeignKey(u'people.id', ondelete='CASCADE'), nullable=False)
    category_id = Column(ForeignKey(u'categories.id'), nullable=False)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum('active', u'disabled'), nullable=False)

    category = relationship('Category')
    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'location_uid', cascade='all, delete-orphan'))

    def as_dict(self):
        return {col.name: getattr(self, col.name)
                for col in self.__table__.columns}


class Message(Base):
    __tablename__ = 'messages'

    id = Column(String(16), primary_key=True, unique=True)
    content = Column(TEXT(), nullable=False)
    subject = Column(String(128))
    sender_id = Column(ForeignKey(u'people.id'), nullable=False)
    recipient_id = Column(ForeignKey(u'people.id'))
    # TODO use the many-to-many table instead
    list_id = Column(ForeignKey(u'lists.id'))
    privacy = Column(String(8), nullable=False, server_default=u'secret')
    published = Column(BOOLEAN)
    uid = Column(ForeignKey(u'people.id', ondelete='CASCADE'), nullable=False)
    viewed = Column(TIMESTAMP)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum('active', u'disabled'), nullable=False,
                    server_default=u'active')

    list = relationship('List')
    owner = relationship('Person', foreign_keys=[uid])
    recipient = relationship('Person', foreign_keys=[recipient_id])

    def as_dict(self):
        return {col.name: getattr(self, col.name)
                for col in self.__table__.columns}


class Person(Base):
    __tablename__ = 'people'

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(64), nullable=False)
    identity = Column(String(64), nullable=False, unique=True)
    referrer_id = Column(ForeignKey(u'people.id'))
    privacy = Column(String(8), nullable=False, server_default=u'public')
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum('active', u'disabled', u'suspended'), nullable=False)

    lists = relationship('List', secondary='listmembers',
                         backref=backref('lists'), lazy='dynamic')
    profile = relationship('Profile')

    def as_dict(self):
        retval = {col.name: getattr(self, col.name)
                  for col in self.__table__.columns}
        retval['lists'] = [list.id for list in self.lists]
        return retval


class Profile(Base):
    __tablename__ = 'profileitems'
    __table_args__ = (
        UniqueConstraint(u'uid', u'item', name='uniq_itemuid'),
    )

    id = Column(String(16), primary_key=True, unique=True)
    uid = Column(ForeignKey(u'people.id'), nullable=False)
    item = Column(Enum(u'birthday', u'employer', u'gender', u'hometown',
                       u'jobtitle', u'lang', u'location', u'partner',
                       u'album', u'reminders', u'tz'), nullable=False)
    value = Column(String(32))
    location_id = Column(ForeignKey(u'locations.id'))
    tz_id = Column(ForeignKey(u'time_zone_name.id'))
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum('active', u'disabled'), nullable=False)

    location = relationship('Location')
    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'profileitems', cascade='all, delete-orphan'))
    tz = relationship('TZname')

    def as_dict(self):
        return {col.name: getattr(self, col.name)
                for col in self.__table__.columns}


class Settings(Base):
    __tablename__ = 'settings'

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(32), nullable=False)
    privacy = Column(String(8), nullable=False, server_default=u'public')
    smtp_port = Column(INTEGER, nullable=False, server_default='25')
    smtp_smarthost = Column(String(255))
    smtp_credential_id = Column(ForeignKey(u'credentials.id'))
    country = Column(String(2), nullable=False,
                     server_default=constants.DEFAULT_COUNTRY)
    default_storage_id = Column(ForeignKey(u'storageitems.id'))
    lang = Column(String(6), nullable=False,
                  server_default=constants.DEFAULT_LANG)
    tz_id = Column(ForeignKey(u'time_zone_name.id'), nullable=False,
                   server_default='598')
    url = Column(String(255))
    window_title = Column(String(127),
                          server_default=constants.WINDOW_TITLE)
    default_cat_id = Column(ForeignKey(u'categories.id'), nullable=False)
    administrator_id = Column(ForeignKey(u'people.id'), nullable=False)
    default_hostlist_id = Column(ForeignKey(u'lists.id'))
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)

    smtp_credential = relationship('Credential',
                                   foreign_keys=[smtp_credential_id])
    default_category = relationship('Category', foreign_keys=[default_cat_id])
    administrator = relationship('Person')
    default_hostlist = relationship('List',
                                    foreign_keys=[default_hostlist_id])
    tz = relationship('TZname')

    def as_dict(self):
        return {col.name: getattr(self, col.name)
                for col in self.__table__.columns}


class Storage(Base):
    __tablename__ = 'storageitems'
    __table_args__ = (
        UniqueConstraint(u'name', u'uid', name='uniq_storage_user'),
    )

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(32), nullable=False)
    prefix = Column(String(128))
    bucket = Column(String(64), nullable=False)
    region = Column(String(16),
                    server_default=constants.DEFAULT_AWS_REGION)
    cdn_uri = Column(String(64))
    identifier = Column(String(64))
    privacy = Column(String(8), nullable=False, server_default=u'public')
    credentials_id = Column(ForeignKey(u'credentials.id'))
    uid = Column(ForeignKey(u'people.id', ondelete='CASCADE'), nullable=False)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum('active', u'disabled'), nullable=False,
                    server_default="active")

    credentials = relationship('Credential')
    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'storage_uid', cascade='all, delete-orphan'))

    def as_dict(self):
        return {col.name: getattr(self, col.name)
                for col in self.__table__.columns}


class TZname(Base):
    __tablename__ = 'time_zone_name'

    id = Column(INTEGER, primary_key=True, unique=True)
    name = Column(String(32), nullable=False, unique=True)
    status = Column(Enum('active', u'disabled'), nullable=False,
                    server_default="active")

    def as_dict(self):
        return {col.name: getattr(self, col.name)
                for col in self.__table__.columns}


class AlembicVersion(Base):
    __tablename__ = 'alembic_version'

    version_num = Column(String(32), primary_key=True, nullable=False)
