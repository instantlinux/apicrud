"""send.py

created 18-apr-2019 by richb@instantlinux.net
"""

import celery
from flask_babel import _
import logging
import smtplib
from sqlalchemy.orm.exc import NoResultFound
import ssl

from ..account_settings import AccountSettings
from ..database import get_session
from ..exceptions import APIcrudSendError
from ..metrics import Metrics
from ..service_config import ServiceConfig
from ..utils import utcnow
from .format import MessageFormat


class Messaging(object):
    """
    External messaging

    Args:
        account_id (str): ID of logged-in account
        db_session (obj): open session to database
        settings (obj): AccountSettings for account
        smtp (obj): open session to SMTP smarthost
        ssl_context (obj): an SSL context (TLSv1_2)
    """
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)

    def __init__(self, db_session=None, account_id=None, smtp=None,
                 settings=None):
        self.config = config = ServiceConfig().config
        self.db_session = db_session or get_session(
            scopefunc=celery.utils.threads.get_ident, db_url=config.DB_URL)
        self.models = ServiceConfig().models
        self.settings = settings or self._get_settings(
            self.models.Account, account_id=account_id)
        self.siteurl = self.settings.get.url
        self.smtp = smtp

    def __del__(self):
        if self.smtp:
            self.smtp.quit()
        self.db_session.remove()

    def send(self, frm=None, to=None, to_uid=None, template=None,
             attachments=[], **kwargs):
        """
        Send a message to one contact

        Args:
            frm (uid): person
            to (Contact): recipient (specific contact address)
            to_uid (uid): recipient (generic, use primary contact)
            template (str): jinja2 template name
            attachments (list): additional MIMEBase / MimeText objects
            kwargs: kv pairs
        Raises:
            APIcrudSendError
        """
        try:
            if to:
                to_contact = self.db_session.query(
                    self.models.Contact).filter_by(id=to).one()
            else:
                to_contact = self.db_session.query(
                    self.models.Contact).join(self.models.Person).filter(
                        self.models.Contact.info ==
                        self.models.Person.identity,
                        self.models.Contact.type == 'email',
                        self.models.Contact.status == 'active',
                        self.models.Person.id == to_uid).one().id
        except NoResultFound:
            msg = 'Recipient cid=%s, uid=%s not found' % (to, to_uid)
            logging.error(msg)
            raise APIcrudSendError(msg)
        logmsg = dict(action='send_contact', to_id=to, from_id=frm,
                      info=to_contact.info)
        if to_contact.status == 'disabled':
            logging.info(dict(status='disabled', **logmsg))
            return
        frm, from_contact = self._get_frm(frm, to_contact)
        if from_contact.info in self.settings.get.approved_senders:
            sender_email = from_contact.info
        else:
            sender_email = self.settings.get.sender_email
        if to_contact.type in ('email', 'sms'):
            if not self.smtp:
                self.smtp = self.smtp_session()
            logging.info('action=send_contact template=%s type=%s address=%s' %
                         (template, to_contact.type, to_contact.info))
            metrics = Metrics(uid=frm, db_session=self.db_session)
            if to_contact.type == 'sms':
                if (not metrics.store('sms_daily_total') or
                        not metrics.store('sms_monthly_total')):
                    msg = _(u'daily limit exceeded')
                    logging.info(dict(message=msg, **logmsg))
                    raise APIcrudSendError(msg)
                dest_email = (to_contact.info + '@' +
                              self.config.CARRIER_GATEWAYS[to_contact.carrier])
                body = MessageFormat(db_session=self.db_session,
                                     settings=self.settings).sms(
                    template, from_contact, to_contact, **kwargs)
            else:
                if (not metrics.store('email_daily_total') or
                        not metrics.store('email_monthly_total')):
                    msg = _(u'daily limit exceeded')
                    logging.info(dict(message=msg, **logmsg))
                    raise APIcrudSendError(msg)
                dest_email = to_contact.info
                body = MessageFormat(db_session=self.db_session,
                                     settings=self.settings).email(
                    template, from_contact, sender_email,
                    to_contact, attachments=attachments,
                    contact_id=to_contact.id, **kwargs).as_string()
            self.smtp.sendmail(sender_email, dest_email, body)
            to_contact.last_attempted = utcnow()
            self.db_session.add(to_contact)
        else:
            logging.warning(dict(message='Unsupported type',
                                 contact_type=to_contact.type, **logmsg))
            # self.db_session.remove()
            raise APIcrudSendError('unsupported type=%s' % to_contact.type)
        self.db_session.commit()

    def smtp_session(self):
        """Open an SMTP connection to the account's defined smtp_smarthost

        Args:
            settings (obj): settings object
        Raises:
            APIcrudSendError
        """
        session = smtplib.SMTP(self.settings.get.smtp_smarthost,
                               self.settings.get.smtp_port)
        session.starttls(context=self.ssl_context)
        if (hasattr(self.settings.get, 'smtp_credential_id') and
                self.settings.get.smtp_credential_id):
            try:
                cred = self.db_session.query(self.models.Credential).filter_by(
                    id=self.settings.get.smtp_credential_id).one()
                session.login(cred.key, cred.secret)
            except Exception as ex:
                logging.error(dict(action='send_contact', message=str(ex)))
                # self.db_session.remove()
                raise APIcrudSendError('Credential problem: %s' % str(ex))
        return session

    def _get_settings(self, model, account_id=None):
        if account_id is None:
            try:
                account_id = self.db_session.query(model).filter_by(
                    name='admin').one().id
            except NoResultFound:
                logging.error('action=_get_settings message="Missing admin"')
                raise APIcrudSendError('Missing admin')
        return AccountSettings(account_id, db_session=self.db_session)

    def _get_frm(self, frm, to_contact):
        """Get the from_contact record which matches the to_contact's
        type (sms, email etc)

        Args:
            frm (uid): the sender
            to_contact (obj): Contact record

        Returns: tuple
            frm (uid): sender uid (or administrator if noen)
            from_contact (obj): Contact record
        """
        logmsg = dict(action='_get_frm', from_id=frm, to=to_contact.info)
        if frm is None:
            frm = self.settings.get.administrator_id
        from_contact = None
        Contact = self.models.Contact
        try:
            from_contact = self.db_session.query(Contact).filter_by(
                uid=frm, type=to_contact.type).filter(
                    (Contact.status.in_(['active', 'unconfirmed']))).first()
        except Exception:
            # We don't care at all why this fails; next step catches error
            pass
        if not from_contact:
            try:
                from_contact = self.db_session.query(
                    Contact).filter_by(uid=frm).filter(
                        (Contact.status.in_(['active', 'unconfirmed']))
                        ).order_by(Contact.rank).first()
            except NoResultFound:
                # self.db_session.remove()
                raise APIcrudSendError('Contact for uid=%s not found' % frm)
            if from_contact:
                logging.warning(dict(message='missing contact type', **logmsg))
            else:
                logging.error(dict(message='garbled_from', **logmsg))
                # self.db_session.remove()
                raise APIcrudSendError('uid=%s cannot get From address' % frm)
        return frm, from_contact
