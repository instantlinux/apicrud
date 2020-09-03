"""format.py

MIME and SMS formatting
TODO redesign as a class

created 15-aug-2020 by docker@instantlinux.net
"""

from babel.support import format_datetime, Translations
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid, formatdate
import jinja2
import logging
from sqlalchemy.orm.exc import NoResultFound

from ..service_config import ServiceConfig

jinja2Env = []


class FormatException(Exception):
    pass


def email(template, frm, sender_email, to, settings, db_session,
          attachments=[], **kwargs):
    """Format an email message with mime attachment, in the user's
    profile-determined locale

    Args:
        template (str): jinja2 template name
        frm (Contact): contact of sender
        sender_email (str): destination address
        to (Contact): contact of recipient
        settings (obj): account settings
        db_session (obj): database session
        attachments (list): additional MIMEBase / MimeText objects
        **kwargs: other key=value pairs for jinja2 substitution
    Returns:
        obj: mime object (use .as_string() to convert to message)
    """
    params = dict(
        sender=frm.owner.name, **kwargs)
    Profile = ServiceConfig().models.Profile
    try:
        tz = db_session.query(Profile).filter(
            Profile.uid == to.uid, Profile.item == 'tz').one().value
    except NoResultFound:
        tz = settings.get.tz
    try:
        lang = db_session.query(Profile).filter(
            Profile.uid == to.uid, Profile.item == 'lang').one().value
    except NoResultFound:
        lang = settings.get.lang
    if 'starts' in kwargs:
        params['starts_formatted'] = format_datetime(
            datetime.strptime(kwargs['starts'], '%Y-%m-%dT%H:%M:%S'),
            'EEEE, d MMM Y H:mm a', locale=lang, tzinfo=tz)
    mime = MIMEMultipart('alternative')
    mime['From'] = '%s <%s>' % (frm.owner.name, sender_email)
    if frm.info != sender_email:
        mime['Reply-To'] = '%s <%s>' % (frm.owner.name, frm.info)
    mime['To'] = '%s <%s>' % (to.owner.name, to.info)
    mime['Date'] = formatdate()
    mime['Subject'] = _render_template(template, lang,
                                       selector='subject', **kwargs)
    mime['Message-ID'] = make_msgid()
    mime.attach(MIMEText(
        _render_template(template, lang, selector='email', **params) +
        _render_template('footer', lang, selector='email', **params),
        'plain'))
    mime.attach(MIMEText(
        _render_template(template, lang, selector='html', **params) +
        _render_template('footer', lang, selector='html', **params),
        'html'))
    for item in attachments:
        mime.attach(item)
    return mime


def sms(template, frm, to, settings, db_session, **kwargs):
    """Format an SMS message

    Args:
        template (str): jinja2 template name
        frm (Contact): contact of sender
        to (Contact): contact of recipient
        **kwargs: other key=value pairs for jinja2 substitution
    Returns:
        str: Formatted string content
    """
    Profile = ServiceConfig().models.Profile
    try:
        lang = db_session.query(Profile).filter(
            Profile.uid == to.uid, Profile.item == 'lang').one().value
    except NoResultFound:
        lang = settings.get.lang
    return _render_template(template, lang, selector='sms',
                            sender=frm.owner.name, **kwargs)


def _render_template(template_name, locale, **kwargs):
    """Scan the configured template_folders path looking for the
    template, apply translations from locale, and process
    with jinja2.

    Args:
        template_name (str): filename of template (without .j2)
        locale (str): language/locale string
        kwargs: key/value pairs for template expansion
    Returns:
        str: Rendered content
    """
    global jinja2Env

    config = ServiceConfig().config
    trans = []
    for dir in config.BABEL_TRANSLATION_DIRECTORIES.split(';'):
        trans.append(Translations.load(dir, locale))
    if not jinja2Env:
        for folder in config.TEMPLATE_FOLDERS:
            jinja2Env.append(jinja2.Environment(
                loader=jinja2.FileSystemLoader(searchpath=folder),
                extensions=['jinja2.ext.i18n', 'jinja2.ext.autoescape'],
                autoescape=jinja2.select_autoescape(['html'])
            ))

    for env in jinja2Env:
        try:
            for x in trans:
                env.install_gettext_translations(x)
            return env.get_template(template_name + '.j2').render(**kwargs)
        except jinja2.exceptions.TemplateNotFound:
            continue
    logging.error(dict(message='template not found', template=template_name))
    raise FormatException('template=%s not found' % template_name)
