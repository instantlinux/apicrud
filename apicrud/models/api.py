"""Open-core API model definitions

created 26-mar-2019 by richb@instantlinux.net

license: lgpl-2.1
"""

# coding: utf-8

# from geoalchemy2 import Geometry
from sqlalchemy import BOOLEAN, Column, Enum, ForeignKey, INTEGER, \
     LargeBinary, String, TEXT, TIMESTAMP, Unicode, UniqueConstraint
from sqlalchemy import func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, backref
from sqlalchemy_utils.types.encrypted.encrypted_type import AesEngine, \
    StringEncryptedType

from apicrud.const import Constants
from .base import get_aes_secret, AsDictMixin, Base
core_schema = 'apicrud'
schema_pre = core_schema + '.' if core_schema else ''

# TODO fix foreign-key dependency-cycle settings / credentials / storage
#  see https://docs.sqlalchemy.org/en/14/core
#   /constraints.html#creating-dropping-foreign-key-constraints-via-alter


class AlembicVersionApicrud(Base):
    __tablename__ = 'alembic_version_apicrud'
    version_num = Column(String(32), primary_key=True, nullable=False)


class Account(AsDictMixin, Base):
    __tablename__ = 'accounts'
    __table_args__ = (
        UniqueConstraint(u'id', u'uid', name='uniq_account_user'),
        dict(schema=core_schema),
    )
    __rest_exclude__ = ('backup_codes', 'password', 'totp_secret')
    __rest_hybrid__ = ('totp',)

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(32), nullable=False, unique=True)
    uid = Column(ForeignKey(u'%speople.id' % schema_pre, ondelete='CASCADE'),
                 nullable=False, unique=True)
    password = Column(StringEncryptedType(Unicode, get_aes_secret, AesEngine,
                                          'pkcs5', length=128), nullable=False)
    password_must_change = Column(BOOLEAN, nullable=False,
                                  server_default="False")
    totp_secret = Column(StringEncryptedType(Unicode, get_aes_secret,
                                             AesEngine, 'pkcs5', length=64))
    backup_codes = Column(LargeBinary(256))
    is_admin = Column(BOOLEAN, nullable=False, server_default="False")
    settings_id = Column(ForeignKey(u'%ssettings.id' % schema_pre),
                         nullable=False)
    last_login = Column(TIMESTAMP)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum(u'active', u'disabled'), nullable=False)

    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'account_uid', cascade='all, delete-orphan'))
    settings = relationship('Settings')

    @hybrid_property
    def totp(self):
        return True if self.totp_secret else False


class APIkey(AsDictMixin, Base):
    __tablename__ = 'apikeys'
    __table_args__ = (
        UniqueConstraint(u'uid', u'name', name='uniq_apikey_owner'),
        dict(schema=core_schema),
    )
    __rest_exclude__ = ('hashvalue',)
    __rest_related__ = ('scopes',)

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(32), nullable=False)
    uid = Column(ForeignKey(u'%speople.id' % schema_pre, ondelete='CASCADE'),
                 nullable=False)
    prefix = Column(String(8), nullable=False, unique=True)
    hashvalue = Column(StringEncryptedType(Unicode, get_aes_secret, AesEngine,
                                           'pkcs5', length=96), nullable=False)
    expires = Column(TIMESTAMP)
    last_used = Column(TIMESTAMP)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum(u'active', u'disabled'), nullable=False,
                    server_default=u'active')

    scopes = relationship('Scope', secondary='%sapikeyscopes' % schema_pre,
                          backref=backref('scope'), order_by='Scope.name')
    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'apikey_uid', cascade='all, delete-orphan'))


class APIkeyScope(Base):
    __tablename__ = 'apikeyscopes'
    __table_args__ = (
        UniqueConstraint(u'apikey_id', u'scope_id', name='uniq_apikey_scope'),
        dict(schema=core_schema),
    )

    apikey_id = Column(
        ForeignKey(u'%sapikeys.id' % schema_pre, ondelete='CASCADE'),
        primary_key=True, nullable=False)
    scope_id = Column(
        ForeignKey(u'%sscopes.id' % schema_pre, ondelete='CASCADE'),
        primary_key=True, nullable=False, index=True)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())

    apikey = relationship('APIkey', foreign_keys=[apikey_id], backref=backref(
        'apikeyscopes', cascade='all, delete-orphan'))
    scope = relationship('Scope', backref=backref(
        'apikeyscopes', cascade='all, delete-orphan'))


class Category(AsDictMixin, Base):
    __tablename__ = 'categories'
    __table_args__ = (
        UniqueConstraint(u'name', u'uid', name='uniq_category_owner'),
        dict(schema=core_schema),
    )

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(64), nullable=False)
    uid = Column(ForeignKey(u'%speople.id' % schema_pre), nullable=False)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum('active', u'disabled'), nullable=False,
                    server_default=u'active')

    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'category_uid', cascade='all, delete-orphan'))


class Contact(AsDictMixin, Base):
    __tablename__ = 'contacts'
    __table_args__ = (
        UniqueConstraint(u'info', u'type', name='uniq_info_type'),
        dict(schema=core_schema),
    )

    id = Column(String(16), primary_key=True, unique=True)
    label = Column(String(16), nullable=False, server_default=u'home')
    type = Column(String(12), nullable=False, server_default=u'email')
    carrier = Column(String(16))
    info = Column(String(255))
    muted = Column(BOOLEAN, nullable=False, server_default="False")
    rank = Column(INTEGER, nullable=False, server_default="1")
    uid = Column(ForeignKey(u'%speople.id' % schema_pre, ondelete='CASCADE'),
                 nullable=False, index=True)
    privacy = Column(String(8), nullable=False, server_default=u'member')
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum(u'active', u'unconfirmed', u'disabled'),
                    nullable=False, server_default=u'unconfirmed')

    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'contacts', cascade='all, delete-orphan'))


class Credential(AsDictMixin, Base):
    __tablename__ = 'credentials'
    __table_args__ = (
        UniqueConstraint(u'name', u'uid', name='uniq_name_uid'),
        dict(schema=core_schema),
    )
    __rest_exclude__ = ('secret', 'otherdata')

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(64), nullable=False)
    vendor = Column(String(32), nullable=False)
    # placeholder field TODO make clear how this will be used
    #  probably to delegate to Secrets Manager / KMS
    type = Column(String(16))
    url = Column(String(length=64))
    key = Column(String(length=128))
    secret = Column(StringEncryptedType(Unicode, get_aes_secret, AesEngine,
                                        'pkcs5', length=128))
    otherdata = Column(StringEncryptedType(Unicode, get_aes_secret, AesEngine,
                                           'pkcs5', length=1024))
    expires = Column(TIMESTAMP)
    settings_id = Column(ForeignKey(u'%ssettings.id' % schema_pre),
                         nullable=False)
    uid = Column(ForeignKey(u'%speople.id' % schema_pre, ondelete='CASCADE'),
                 nullable=False)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum(u'active', u'disabled'), nullable=False,
                    server_default=u'active')

    settings = relationship('Settings', foreign_keys=[settings_id])
    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'credential_uid', cascade='all, delete-orphan'))


class Grant(AsDictMixin, Base):
    __tablename__ = 'grants'
    __table_args__ = (
        UniqueConstraint(u'name', u'uid', name='uniq_grant_user'),
        dict(schema=core_schema),
    )

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(24), nullable=False)
    value = Column(String(64), nullable=False)
    uid = Column(ForeignKey(u'%speople.id' % schema_pre), nullable=False)
    expires = Column(TIMESTAMP)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum('active', u'disabled'), nullable=False,
                    server_default=u'active')

    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'grant_uid', cascade='all, delete-orphan'))


class List(AsDictMixin, Base):
    __tablename__ = 'lists'
    __table_args__ = (
        UniqueConstraint(u'name', u'uid', name='uniq_list_owner'),
        dict(schema=core_schema),
    )
    __rest_related__ = ('members',)

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(64), nullable=False)
    description = Column(TEXT())
    privacy = Column(String(8), nullable=False, server_default=u'secret')
    category_id = Column(ForeignKey(u'%scategories.id' % schema_pre),
                         nullable=False)
    uid = Column(ForeignKey(u'%speople.id' % schema_pre, ondelete='CASCADE'),
                 nullable=False)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum('active', u'disabled'), nullable=False)

    members = relationship('Person', secondary='listmembers',
                           backref=backref('people'), order_by='Person.name')
    # messages = relationship('Message', secondary='listmessages',
    #                         backref=backref('lists'),
    #                         order_by='Message.created')
    category = relationship('Category')
    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'list_uid', cascade='all, delete-orphan'))


# see https://docs.sqlalchemy.org/en/13/orm/extensions/associationproxy.html
class ListMember(Base):
    __tablename__ = 'listmembers'
    __table_args__ = (
        UniqueConstraint(u'list_id', u'uid', name='uniq_listmember'),
    )

    uid = Column(ForeignKey(u'%speople.id' % schema_pre, ondelete='CASCADE'),
                 primary_key=True, nullable=False)
    list_id = Column(
        ForeignKey(u'%slists.id' % schema_pre, ondelete='CASCADE'),
        primary_key=True, nullable=False, index=True)
    authorization = Column(String(8), nullable=False,
                           server_default=u'member')
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())

    person = relationship('Person', foreign_keys=[uid], backref=backref(
        'listmembers', cascade='all, delete-orphan'))
    list = relationship('List', backref=backref(
        'listmembers', cascade='all, delete-orphan'))


class Location(AsDictMixin, Base):
    __tablename__ = 'locations'
    __table_args__ = (
        dict(schema=core_schema),
    )

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(255))
    address = Column(String(255))
    city = Column(String(64), nullable=False)
    state = Column(String(16))
    postalcode = Column(String(12))
    country = Column(String(2), nullable=False,
                     server_default=Constants.DEFAULT_COUNTRY)
    # MariaDB is not supported by geoalchemy2, alas
    # geo = Column(Geometry(geometry_type='POINT'))
    # Coordinates are stored as fixed-precision (divide by 1e7)
    geolat = Column(INTEGER)
    geolong = Column(INTEGER)
    neighborhood = Column(String(32))
    privacy = Column(String(8), nullable=False, server_default=u'public')
    uid = Column(ForeignKey(u'%speople.id' % schema_pre, ondelete='CASCADE'),
                 nullable=False)
    category_id = Column(ForeignKey(u'%scategories.id' % schema_pre),
                         nullable=False)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum('active', u'disabled'), nullable=False)

    category = relationship('Category')
    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'location_uid', cascade='all, delete-orphan'))


class Person(AsDictMixin, Base):
    __tablename__ = 'people'
    __table_args__ = (
        dict(schema=core_schema),
    )
    __rest_related__ = ('lists',)

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(64), nullable=False)
    identity = Column(String(64), nullable=False, unique=True)
    referrer_id = Column(ForeignKey(u'%speople.id' % schema_pre))
    privacy = Column(String(8), nullable=False, server_default=u'public')
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum('active', u'disabled', u'suspended'), nullable=False)

    lists = relationship('List', secondary='listmembers',
                         backref=backref('lists'), lazy='dynamic')
    profileitems = relationship('Profile', backref=backref(
        '%sprofileitems' % schema_pre))


class Profile(AsDictMixin, Base):
    __tablename__ = 'profileitems'
    __table_args__ = (
        UniqueConstraint(u'uid', u'item', name='uniq_itemuid'),
        dict(schema=core_schema),
    )

    id = Column(String(16), primary_key=True, unique=True)
    uid = Column(ForeignKey(u'%speople.id' % schema_pre, ondelete='CASCADE'),
                 nullable=False)
    item = Column(String(32), nullable=False)
    value = Column(String(96))
    location_id = Column(ForeignKey(u'%slocations.id' % schema_pre))
    tz_id = Column(ForeignKey(u'%stime_zone_name.id' % schema_pre))
    privacy = Column(String(8), nullable=False, server_default=u'public')
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum('active', u'disabled'), nullable=False)

    location = relationship('Location')
    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'profile', cascade='all, delete-orphan'))
    tz = relationship('Tz')


class Scope(AsDictMixin, Base):
    __tablename__ = 'scopes'
    __table_args__ = (
        UniqueConstraint(u'name', u'settings_id', name='uniq_scope_name'),
        dict(schema=core_schema),
    )

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(32), nullable=False)
    settings_id = Column(ForeignKey(u'%ssettings.id' % schema_pre),
                         nullable=False)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum('active', u'disabled'), nullable=False,
                    server_default=u'active')


class Settings(AsDictMixin, Base):
    __tablename__ = 'settings'
    __table_args__ = (
        dict(schema=core_schema),
    )

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(32), nullable=False)
    privacy = Column(String(8), nullable=False, server_default=u'public')
    smtp_port = Column(INTEGER, nullable=False, server_default='25')
    smtp_smarthost = Column(String(255))
    smtp_credential_id = Column(ForeignKey(
        u'%scredentials.id' % schema_pre, use_alter=True, name='settings_fk1'))
    country = Column(String(2), nullable=False,
                     server_default=Constants.DEFAULT_COUNTRY)
    # TODO storage is for media, need to refactor Settings as a many-to-many
    # like ProfileItems
    default_storage_id = Column(ForeignKey(u'%sstorageitems.id' % schema_pre))
    lang = Column(String(6), nullable=False,
                  server_default=Constants.DEFAULT_LANG)
    tz_id = Column(ForeignKey(u'%stime_zone_name.id' % schema_pre),
                   nullable=False, server_default='598')
    url = Column(String(255))
    window_title = Column(String(127),
                          server_default=Constants.DEFAULT_WINDOW_TITLE)
    default_cat_id = Column(ForeignKey(u'%scategories.id' % schema_pre),
                            nullable=False)
    administrator_id = Column(ForeignKey(u'%speople.id' % schema_pre),
                              nullable=False)
    default_hostlist_id = Column(ForeignKey(u'%slists.id' % schema_pre))
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)

    smtp_credential = relationship('Credential',
                                   foreign_keys=[smtp_credential_id])
    default_category = relationship('Category', foreign_keys=[default_cat_id])
    administrator = relationship('Person')
    default_hostlist = relationship('List',
                                    foreign_keys=[default_hostlist_id])
    tz = relationship('Tz')


class Storage(AsDictMixin, Base):
    __tablename__ = 'storageitems'
    __table_args__ = (
        UniqueConstraint(u'name', u'uid', name='uniq_storage_user'),
        dict(schema=core_schema),
    )

    id = Column(String(16), primary_key=True, unique=True)
    name = Column(String(32), nullable=False)
    prefix = Column(String(128))
    bucket = Column(String(64), nullable=False)
    region = Column(String(16),
                    server_default=Constants.DEFAULT_AWS_REGION)
    cdn_uri = Column(String(64))
    identifier = Column(String(64))
    privacy = Column(String(8), nullable=False, server_default=u'public')
    credentials_id = Column(ForeignKey(u'%scredentials.id' % schema_pre))
    uid = Column(ForeignKey(u'%speople.id' % schema_pre, ondelete='CASCADE'),
                 nullable=False)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum('active', u'disabled'), nullable=False,
                    server_default="active")

    credentials = relationship('Credential')
    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'storage_uid', cascade='all, delete-orphan'))


class Tz(AsDictMixin, Base):
    __tablename__ = 'time_zone_name'
    __table_args__ = (
        dict(schema=core_schema),
    )

    id = Column(INTEGER, primary_key=True, unique=True)
    name = Column(String(32), nullable=False, unique=True)
    status = Column(Enum('active', u'disabled'), nullable=False,
                    server_default="active")
