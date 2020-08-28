"""send.py

Send a message

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


def to_contact(db_session, frm=None, to=None, template=None,
               account_id=None, **kwargs):
    """
    Args:
      db_session (obj): open session to database
      frm (uid): person
      to (Contact): recipient
      template (str): jinja2 template name
      account_id (str): ID of logged-in account
      kwargs: kv pairs
    Raises:
      SendException
    """

    config = ServiceConfig().config
    models = ServiceConfig().models
    settings = _get_settings(db_session, models.Account, account_id=account_id)
    to_contact = db_session.query(models.Contact).filter_by(id=to).one()
    logmsg = dict(action='send_contact', to_id=to, from_id=frm,
                  info=to_contact.info)
    if to_contact.status == 'disabled':
        logging.info(dict(status='disabled', **logmsg))
        return
    if frm is None:
        frm = settings.get.administrator_id
    from_contact = None
    try:
        from_contact = db_session.query(models.Contact).filter_by(
            uid=frm, type=to_contact.type).filter(
                (models.Contact.status.in_(['active', 'unconfirmed']))).first()
    except Exception:
        # We don't care at all why this fails; next step catches error
        pass
    if not from_contact:
        try:
            from_contact = db_session.query(models.Contact).filter_by(
                uid=frm).filter(
                    (models.Contact.status.in_(['active', 'unconfirmed']))
                    ).order_by(models.Contact.rank).first()
        except NoResultFound:
            raise SendException('Contact for uid=%s not found' % frm)
        if from_contact:
            logging.warning(dict(message='missing contact type', **logmsg))
        else:
            logging.error(dict(message='garbled_from', **logmsg))
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
            if (hasattr(settings.get, 'smtp_credential_id') and
                    settings.get.smtp_credential_id):
                try:
                    cred = db_session.query(models.Credential).filter_by(
                        id=settings.get.smtp_credential_id).one()
                    smtp.login(cred.key, cred.secret)
                except Exception as ex:
                    logging.error('action=send_contact message=%s' %
                                  str(ex))
                    db_session.remove()
                    raise
            logging.info('action=send_contact id=%s type=%s address=%s' %
                         (to, to_contact.type, to_contact.info))
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
                    appname=config.APPNAME,
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


def _get_settings(db_session, model, account_id=None):
    if account_id is None:
        try:
            account_id = db_session.query(model).filter_by(
                name='admin').one().id
        except NoResultFound:
            logging.warning('action=_get_settings message="Missing admin"')
            raise SendException('Missing admin')
    return AccountSettings(account_id, db_session=db_session)
