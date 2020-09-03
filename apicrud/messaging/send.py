"""send.py

Send a message
TODO redesign this as a class, it evolved from the oldest crappy script

created 18-apr-2019 by richb@instantlinux.net
"""

from datetime import datetime
import logging
import smtplib
from sqlalchemy.orm.exc import NoResultFound
import ssl

from ..account_settings import AccountSettings
from ..service_config import ServiceConfig
import apicrud.messaging.format

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)


class SendException(Exception):
    pass


def to_contact(db_session, smtp=None, frm=None, to=None, template=None,
               account_id=None, settings=None, attachments=[], **kwargs):
    """
    Args:
        db_session (obj): open session to database
        smtp (obj): open session to SMTP smarthost
        frm (uid): person
        to (Contact): recipient
        template (str): jinja2 template name
        account_id (str): ID of logged-in account
        settings (obj): the AccountSettings for the account
        attachments (list): additional MIMEBase / MimeText objects
        kwargs: kv pairs
    Raises:
        SendException
    """

    config = ServiceConfig().config
    models = ServiceConfig().models
    if not settings:
        settings = _get_settings(db_session,
                                 models.Account, account_id=account_id)
    smtp_persist = True if smtp else False
    to_contact = db_session.query(models.Contact).filter_by(id=to).one()
    logmsg = dict(action='send_contact', to_id=to, from_id=frm,
                  info=to_contact.info)
    if to_contact.status == 'disabled':
        logging.info(dict(status='disabled', **logmsg))
        return
    frm, from_contact = _get_frm(frm, to_contact, settings, db_session)
    if from_contact.info in settings.get.approved_senders:
        sender_email = from_contact.info
    else:
        sender_email = settings.get.sender_email
    if to_contact.type in ('email', 'sms'):
        if not smtp:
            smtp = smtp_session(settings, db_session)
        logging.info('action=send_contact template=%s type=%s address=%s' %
                     (template, to_contact.type, to_contact.info))
        if to_contact.type == 'sms':
            dest_email = (to_contact.info + '@' +
                          config.CARRIER_GATEWAYS[to_contact.carrier])
            body = apicrud.messaging.format.sms(
                template, from_contact, to_contact, settings,
                db_session, appname=config.APPNAME,
                siteurl=settings.get.url, **kwargs)
        else:
            dest_email = to_contact.info
            body = apicrud.messaging.format.email(
                template, from_contact, sender_email,
                to_contact, settings, db_session,
                attachments=attachments, appname=config.APPNAME,
                contact_id=to_contact.id,
                siteurl=settings.get.url, **kwargs).as_string()
        smtp.sendmail(settings.get.sender_email, dest_email, body)
        to_contact.last_attempted = datetime.utcnow()
        db_session.add(to_contact)
    else:
        logging.warning(dict(message='Unsupported type',
                             contact_type=to_contact.type, **logmsg))
        db_session.remove()
        raise SendException('unsupported type=%s' % to_contact.type)
    db_session.commit()
    if not smtp_persist:
        smtp.quit()


def smtp_session(settings, db_session):
    """Open an SMTP connection to the account's defined smtp_smarthost

    Args:
        settings (obj): settings object
    """
    models = ServiceConfig().models
    session = smtplib.SMTP(settings.get.smtp_smarthost,
                           settings.get.smtp_port)
    session.starttls(context=ssl_context)
    if (hasattr(settings.get, 'smtp_credential_id') and
            settings.get.smtp_credential_id):
        try:
            cred = db_session.query(models.Credential).filter_by(
                id=settings.get.smtp_credential_id).one()
            session.login(cred.key, cred.secret)
        except Exception as ex:
            logging.error('action=send_contact message=%s' %
                          str(ex))
            db_session.remove()
        raise
    return session


def _get_settings(db_session, model, account_id=None):
    if account_id is None:
        try:
            account_id = db_session.query(model).filter_by(
                name='admin').one().id
        except NoResultFound:
            logging.warning('action=_get_settings message="Missing admin"')
            raise SendException('Missing admin')
    return AccountSettings(account_id, db_session=db_session)


def _get_frm(frm, to_contact, settings, db_session):
    """TODO this is a BS function to get rid of Improve encapsulation

    Args:
        frm (uid): the sender
        to_contact (obj): Contact record
        settings (obj): settings object
        db_session (obj): an db session
    """
    logmsg = dict(action='_get_frm', from_id=frm, to=to_contact.info)
    if frm is None:
        frm = settings.get.administrator_id
    from_contact = None
    Contact = ServiceConfig().models.Contact
    try:
        from_contact = db_session.query(Contact).filter_by(
            uid=frm, type=to_contact.type).filter(
                (Contact.status.in_(['active', 'unconfirmed']))).first()
    except Exception:
        # We don't care at all why this fails; next step catches error
        pass
    if not from_contact:
        try:
            from_contact = db_session.query(Contact).filter_by(uid=frm).filter(
                    (Contact.status.in_(['active', 'unconfirmed']))
                    ).order_by(Contact.rank).first()
        except NoResultFound:
            db_session.remove()
            raise SendException('Contact for uid=%s not found' % frm)
        if from_contact:
            logging.warning(dict(message='missing contact type', **logmsg))
        else:
            logging.error(dict(message='garbled_from', **logmsg))
            db_session.remove()
            raise SendException('uid=%s cannot get From address' % frm)
    return frm, from_contact
