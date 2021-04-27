"""messaging.py

Celery worker to process outbound messaging

created 18-apr-2019 by richb@instantlinux.net
"""

import celery
import os

from apicrud import Metrics, ServiceConfig
from apicrud.messaging.send import Messaging

import celeryconfig
import models

# TODO add function to send to a recipients list

app = celery.Celery()
app.config_from_object(celeryconfig)
path = os.path.dirname(os.path.abspath(__file__))
config = ServiceConfig(
    babel_translation_directories='i18n;%s' % os.path.join(path, 'i18n'),
    file=os.path.join(path, 'config.yaml'), models=models, reset=True,
    template_folders=[os.path.join(path, 'templates')]).config


@app.task(name='tasks.messaging.send_contact')
def send_contact(frm=None, to=None, to_uid=None, template=None, **kwargs):
    """
    Args:
      frm (uid): person
      to (Contact): recipient
      template (str): jinja2 template name
      kwargs: kv pairs
    Raises:
      SendException
    """
    Messaging().send(
        frm=frm, to=to, to_uid=to_uid, template=template, **kwargs)


# Register send_contact, for usage-alert notifications
Metrics(func_send=send_contact.delay)
