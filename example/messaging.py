"""messaging.py

Celery worker to process outbound messaging

created 18-apr-2019 by richb@instantlinux.net
"""

import celery
import os

from apicrud import ServiceConfig
from apicrud.messaging.send import Messaging

import celeryconfig
import models

# TODO add function to send to a recipients list

app = celery.Celery()
app.config_from_object(celeryconfig)
path = os.path.dirname(os.path.abspath(__file__))
config = ServiceConfig(
    reset=True, models=models, file=os.path.join(path, 'config.yaml'),
    template_folders=[os.path.join(path, 'templates')]).config


@app.task(name='tasks.messaging.send_contact')
def send_contact(frm=None, to=None, template=None, **kwargs):
    """
    Args:
      frm (uid): person
      to (Contact): recipient
      template (str): jinja2 template name
      kwargs: kv pairs
    Raises:
      SendException
    """
    Messaging().send(frm=frm, to=to, template=template, **kwargs)
