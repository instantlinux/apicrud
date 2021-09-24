"""Open-core API model definitions

created 26-mar-2019 by richb@instantlinux.net

license: lgpl-2.1
"""

# coding: utf-8

from sqlalchemy import BOOLEAN, Column, Enum, ForeignKey, String, TEXT, \
    TIMESTAMP, UniqueConstraint
from sqlalchemy import func
from sqlalchemy.orm import relationship, backref

from apicrud.models.base import AsDictMixin, Base
app_schema = 'main'
schema_pre = app_schema + '.' if app_schema else ''
core_pre = 'apicrud.' if app_schema else ''


class DirectMessage(Base):
    __tablename__ = 'directmessages'
    __table_args__ = (
        UniqueConstraint(u'message_id', u'uid', name='uniq_directmessage'),
        dict(schema=app_schema),
    )

    message_id = Column(ForeignKey(u'%smessages.id' % schema_pre,
                                   ondelete='CASCADE'),
                        primary_key=True, nullable=False)
    uid = Column(ForeignKey(u'%speople.id' % core_pre, ondelete='CASCADE'),
                 primary_key=True, nullable=False, index=True)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())

    owner = relationship('Person', foreign_keys=[uid], backref=backref(
        'directmessages', cascade='all, delete-orphan'))
    message = relationship('Message', backref=backref(
        'directmessages', cascade='all, delete-orphan'))


class ListMessage(Base):
    __tablename__ = 'listmessages'
    __table_args__ = (
        UniqueConstraint(u'list_id', u'message_id', name='uniq_listmessage'),
        dict(schema=app_schema),
    )

    message_id = Column(ForeignKey(u'%smessages.id' % schema_pre,
                                   ondelete='CASCADE'),
                        primary_key=True, nullable=False)
    list_id = Column(ForeignKey(u'%slists.id' % core_pre, ondelete='CASCADE'),
                     primary_key=True, nullable=False, index=True)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())

    message = relationship(
        'Message', foreign_keys=[message_id], backref=backref(
            'listmessages', cascade='all, delete-orphan'))
    list = relationship('List', backref=backref(
        'listmessages', cascade='all, delete-orphan'))


class Message(AsDictMixin, Base):
    __tablename__ = 'messages'
    __table_args__ = (
        dict(schema=app_schema),
    )

    id = Column(String(16), primary_key=True, unique=True)
    content = Column(TEXT(), nullable=False)
    subject = Column(String(128))
    sender_id = Column(ForeignKey(u'%speople.id' % core_pre), nullable=False)
    recipient_id = Column(ForeignKey(u'%speople.id' % core_pre))
    # TODO use the many-to-many table instead
    list_id = Column(ForeignKey(u'%slists.id' % core_pre))
    privacy = Column(String(8), nullable=False, server_default=u'secret')
    published = Column(BOOLEAN)
    uid = Column(ForeignKey(u'%speople.id' % core_pre, ondelete='CASCADE'),
                 nullable=False)
    viewed = Column(TIMESTAMP)
    created = Column(TIMESTAMP, nullable=False, server_default=func.now())
    modified = Column(TIMESTAMP)
    status = Column(Enum('active', u'disabled'), nullable=False,
                    server_default=u'active')

    list = relationship('List')
    owner = relationship('Person', foreign_keys=[uid])
    recipient = relationship('Person', foreign_keys=[recipient_id])
