"""messaging.py

Celery worker to process outbound messaging

created 18-apr-2019 by richb@instantlinux.net
"""

import celery
import os

from apicrud import initialize
from apicrud.messaging.send import Messaging

import celeryconfig
import models

# TODO add function to send to a recipients list

app = celery.Celery()
app.config_from_object(celeryconfig)


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


initialize.worker(models=models,
                  path=os.path.dirname(os.path.abspath(__file__)),
                  func_send=send_contact.delay)
