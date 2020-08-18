"""messaging.py

Celery worker to process outbound messaging

created 18-apr-2019 by richb@instantlinux.net
"""

import celery
import os

from apicrud.database import get_session
from apicrud.service_config import ServiceConfig
import apicrud.messaging.send

import celeryconfig
import i18n_textstrings as i18n
import models

# TODO add function to send to a recipients list

app = celery.Celery()
app.config_from_object(celeryconfig)
config = ServiceConfig(reset=True, file=os.path.join(os.path.dirname(
    os.path.abspath(__file__)), 'config.yaml'), models=models).config


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

    db_session = get_session(scopefunc=celery.utils.threads.get_ident,
                             db_url=config.DB_URL)
    apicrud.messaging.send.to_contact(db_session, i18n, frm=frm, to=to,
                                      template=template, **kwargs)
    db_session.remove()
