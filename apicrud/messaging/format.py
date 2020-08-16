"""format.py

MIME and SMS formatting

created 15-aug-2020 by docker@instantlinux.net
"""

from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid, formatdate
import jinja2
import pytz
from sqlalchemy.orm.exc import NoResultFound

from ..service_config import ServiceConfig

W3_DOCTYPE = '<!DOCTYPE HTML PUBLIC “-//W3C//DTD HTML 3.2//EN”>'


def email(content, frm, sender_email, to, settings, db_session,
          i18n, **kwargs):
    """Format an email message with mime attachment, in the user's
    profile-determined locale

    Args:
        content (str): i18n dict
        frm (Contact): contact of sender
        sender_email (str): destination address
        to (Contact): contact of recipient
        settings (obj): account settings
        db_session: database session
        i18n: localization context
        **kwargs: other key=value pairs for jinja2 substitution

    Returns:
        mime object (the as_string() method will convert to message)
    """
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
    Profile = ServiceConfig().models.Profile
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
    return mime


def sms(content, frm, to, **kwargs):
    """Format an SMS message
        content (str): i18n dict
        frm (Contact): contact of sender
        to (Contact): contact of recipient
        **kwargs: other key=value pairs for jinja2 substitution
    """
    content
    return jinja2.Environment().from_string(content['sms']).render(
        sender=frm.owner.name, **kwargs)
