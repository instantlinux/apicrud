"""messaging.py

Celery worker to process outbound messaging

created 18-apr-2019 by richb@instantlinux.net
"""

import celery
from datetime import datetime
import logging
import os
import smtplib
from sqlalchemy.orm.exc import NoResultFound
import ssl

import celeryconfig
import i18n_textstrings as i18n
import models
from models import Contact, Person, Profile
from apicrud.account_settings import AccountSettings
from apicrud.database import get_session
from apicrud.service_config import ServiceConfig
import apicrud.messaging.format

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
app = celery.Celery()
app.config_from_object(celeryconfig)
config = ServiceConfig(reset=True, file=os.path.join(os.path.dirname(
    os.path.abspath(__file__)), 'config.yaml')).config


class SendException(Exception):
    pass


@app.task(name='tasks.messaging.send')
def send(uid, recipient_ids, template, **kwargs):
    """
    Args:
      uid (Person): uid of host
      recipient_ids (Person): recipients
      template (str): template name, jinja2 from i18n_textstrings
      kwargs: kv pairs for template
    """
    db_session = get_session(scopefunc=celery.utils.threads.get_ident,
                             db_url=config.DB_URL)
    settings = _get_settings(db_session)
    with smtplib.SMTP(settings.get.smtp_smarthost,
                      settings.get.smtp_port) as smtp:
        smtp.starttls(context=ssl_context)
        if settings.get.smtp_credential_id:
            try:
                cred = db_session.query(models.Credential).filter_by(
                    id=settings.get.smtp_credential_id).one()
                smtp.login(cred.key, cred.secret)
            except Exception as ex:
                logging.error('action=send message=%s' % str(ex))
                raise
        count, errors = (0, 0)
        for person in recipient_ids:
            try:
                contacts = [item.id for item in db_session.query(Contact).join(
                    Person, Contact.uid == person).all()
                            if not item.muted and not
                            item.status == 'disabled']
                name = db_session.query(Person).filter_by(id=person).one().name
                try:
                    lang = db_session.query(Profile).filter(
                        Profile.uid == person,
                        Profile.item == 'lang').one().value
                except NoResultFound:
                    lang = settings.get.lang
            except NoResultFound as ex:
                logging.warning('action=send uid=%s message=%s' %
                                (person, str(ex)))
            kwargs.update(dict(name=name, lang=lang))
            for contact in contacts:
                try:
                    send_contact(frm=uid, to=contact, template=template,
                                 db_session=db_session, **kwargs)
                    count += 1
                except SendException:
                    errors += 1
    db_session.remove()
    if errors > 0:
        msg = 'action=send count=%d errors=%d' % (count, errors)
        logging.warning(msg)
        raise SendException(msg)


@app.task(name='tasks.messaging.send_contact')
def send_contact(frm=None, to=None, template=None, db_session=None, **kwargs):
    """
    Args:
      frm (uid): person
      to (Contact): recipient
      template (str): template name, jinja2 from i18n_texstrings
      kwargs: kv pairs
    Raises:
      SendException
    """

    db_clean_needed = False
    if not db_session:
        db_clean_needed = True
        db_session = get_session(scopefunc=celery.utils.threads.get_ident,
                                 db_url=config.DB_URL)
    settings = _get_settings(db_session)
    to_contact = db_session.query(Contact).filter_by(id=to).one()
    logmsg = dict(action='send_contact', to_id=to, from_id=frm,
                  info=to_contact.info)
    if to_contact.status == 'disabled':
        logging.info(dict(status='disabled', **logmsg))
        db_session.remove()
        return
    if frm is None:
        frm = settings.get.administrator_id
    from_contact = None
    try:
        from_contact = db_session.query(Contact).filter_by(
            uid=frm, type=to_contact.type).filter(
                (Contact.status.in_(['active', 'unconfirmed']))).first()
    except Exception:
        # We don't care at all why this fails; next step catches error
        pass
    if not from_contact:
        try:
            from_contact = db_session.query(Contact).filter_by(
                uid=frm).filter(
                    (Contact.status.in_(['active', 'unconfirmed']))
                    ).order_by(Contact.rank).first()
        except NoResultFound:
            raise SendException('Contact for uid=%s not found' % frm)
        if from_contact:
            logging.warning(dict(message='missing contact type', **logmsg))
        else:
            logging.error(dict(message='garbled_from', **logmsg))
            if db_clean_needed:
                db_session.remove()
            raise SendException('uid=%s cannot determine From address' % frm)
    if from_contact.info in settings.get.approved_senders:
        sender_email = from_contact.info
    else:
        sender_email = settings.get.sender_email
    if to_contact.type in ['email', 'sms']:
        with smtplib.SMTP(settings.get.smtp_smarthost,
                          settings.get.smtp_port) as smtp:
            smtp.starttls(context=ssl_context)
            if settings.get.smtp_credential_id:
                try:
                    cred = db_session.query(models.Credential).filter_by(
                        id=settings.get.smtp_credential_id).one()
                    smtp.login(cred.key, cred.secret)
                except Exception as ex:
                    logging.error('action=send_contact message=%s' %
                                  str(ex))
                    raise
            logging.info('action=send_contact id=%s type=%s address=%s' %
                         (to, to_contact.type, to_contact.info))
            if to_contact.type == 'sms':
                dest_email = (to_contact.info + '@' +
                              config.carrier_gateways[to_contact.carrier])
                body = apicrud.messaging.format.sms(
                    i18n.TPL[template], from_contact, to_contact,
                    appname=config.APPNAME,
                    siteurl=settings.get.url, **kwargs)
            else:
                dest_email = to_contact.info
                body = apicrud.messaging.format.email(
                    i18n.TPL[template], from_contact, sender_email,
                    to_contact, settings, db_session,
                    models=models, i18n=i18n,
                    appname=config.APPNAME,
                    contact_id=to_contact.id,
                    siteurl=settings.get.url, **kwargs).as_string()
            smtp.sendmail(settings.get.sender_email, dest_email, body)
            to_contact.last_attempted = datetime.utcnow()
            db_session.add(to_contact)
    else:
        logging.warning(dict(message='Unsupported type',
                             contact_type=to_contact.type, **logmsg))
        raise SendException('unsupported type=%s' % to_contact.type)
    db_session.commit()
    if db_clean_needed:
        db_session.remove()


def _get_settings(db_session, account_id=None):
    if account_id is None:
        try:
            account_id = db_session.query(models.Account).filter_by(
                name='admin').one().id
        except NoResultFound:
            logging.warning('action=_get_settings message="Missing admin"')
            raise SendException('Missing admin')
    return AccountSettings(account_id, models, db_session=db_session)
