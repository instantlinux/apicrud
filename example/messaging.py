"""messaging.py

Celery worker to process outbound messaging

created 18-apr-2019 by richb@instantlinux.net
"""

import celery
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid, formatdate
import jinja2
import logging
import pytz
import smtplib
from sqlalchemy.orm.exc import NoResultFound
import ssl

from example import celeryconfig, config, models
from example import i18n_textstrings as i18n
from example.models import Account, Credential, Contact, Person, Profile
from apicrud.account_settings import AccountSettings
from apicrud.database import get_session

CARRIER_GATEWAY = dict(
    att='txt.att.net',
    sprint='messaging.sprintpcs.com',
    tmobile='tmomail.net',
    verizon='vtext.com')
W3_DOCTYPE = '<!DOCTYPE HTML PUBLIC “-//W3C//DTD HTML 3.2//EN”>'

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
app = celery.Celery()
app.config_from_object(celeryconfig)


class SendException(Exception):
    pass


@app.task(name='tasks.messaging.send')
def send(uid, recipient_ids, template, **kwargs):
    """
    params:
      uid (Person) - uid of host
      recipient_ids (Person) - recipients
      template (str) - template name, jinja2 from i18n_texstrings
      kwargs - kv pairs for template
    """
    db_session = get_session(scopefunc=celery.utils.threads.get_ident,
                             db_url=config.DB_URL)
    settings = _get_settings(db_session)
    with smtplib.SMTP(settings.get.smtp_smarthost,
                      settings.get.smtp_port) as smtp:
        smtp.starttls(context=ssl_context)
        if settings.get.smtp_credential_id:
            try:
                cred = db_session.query(Credential).filter_by(
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
    params:
      frm (uid) - person
      to (Contact) - recipient
      template (str) - template name, jinja2 from i18n_texstrings
      kwargs - kv pairs
    raises:
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
                    cred = db_session.query(Credential).filter_by(
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
                              CARRIER_GATEWAY[to_contact.carrier])
                body = _sms_format(i18n.TPL[template], from_contact,
                                   to_contact,
                                   appname=config.APPNAME,
                                   siteurl=settings.get.url, **kwargs)
            else:
                dest_email = to_contact.info
                body = _email_format(i18n.TPL[template], from_contact,
                                     sender_email,
                                     to_contact, settings, db_session,
                                     appname=config.APPNAME,
                                     contact_id=to_contact.id,
                                     siteurl=settings.get.url, **kwargs)
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


def _email_format(content, frm, sender_email, to, settings, db_session,
                  **kwargs):
    mime = MIMEMultipart('alternative')
    mime['From'] = '%s <%s>' % (frm.owner.name, sender_email)
    if frm.info != sender_email:
        mime['Reply-To'] = '%s <%s>' % (frm.owner.name, frm.info)
    mime['To'] = '%s <%s>' % (to.owner.name, to.info)
    mime['Date'] = formatdate()
    mime['Subject'] = content['subject'] % kwargs
    mime['Message-ID'] = make_msgid()
    params = dict(
        sender=frm.owner.name, **kwargs)
    try:
        tzval = db_session.query(Profile).filter(
            Profile.uid == to.uid, Profile.item == 'tz').one().tz
        tz = pytz.timezone(tzval)
    except NoResultFound:
        tz = pytz.timezone(settings.get.tz)
    if 'starts' in kwargs:
        params['starts_formatted'] = datetime.strftime(
            pytz.utc.localize(datetime.strptime(
                kwargs['starts'], '%Y-%m-%dT%H:%M:%S')).astimezone(tz),
            '%A, %d %B %Y %-I:%M %p')
    mime.attach(MIMEText(jinja2.Environment().from_string(
        content['email'] + i18n.TPL_FOOTER['email']).render(params), 'plain'))
    mime.attach(MIMEText(jinja2.Environment().from_string(
        W3_DOCTYPE +
        content['html'] + i18n.TPL_FOOTER['html']).render(params), 'html'))
    return mime.as_string()


def _sms_format(content, frm, to, **kwargs):
    return jinja2.Environment().from_string(content['sms']).render(
        sender=frm.owner.name, **kwargs)


def _get_settings(db_session, account_id=None):
    if account_id is None:
        try:
            account_id = db_session.query(Account).filter_by(
                name='admin').one().id
        except NoResultFound:
            logging.warning('action=_get_settings message="Missing admin"')
            raise SendException('Missing admin')
    return AccountSettings(account_id, config, models, db_session=db_session)


def _replace_last_comma_and(string, lang):
    """
    Replace the last comma with the word 'and', dealing with translation.
    The string is presumed to be a text array joined by ', ' -- including
    the space.
    """

    i = string.rfind(',')
    conjunction = dict(
        es=u'y', de=u'und', fr=u'et', pt=u'e', zh=u'和').get(lang, u'and')
    if i == -1:
        return string
    else:
        return string[:i] + ' ' + conjunction + string[i + 1:]
