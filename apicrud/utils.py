"""utils.py

Utilities
  Miscellaneous utility functions that don't fit elsewhere

created 11-apr-2020 by richb@instantlinux.net
"""
from datetime import datetime
from flask import g
from html.parser import HTMLParser
import random
import re
import string


def gen_id(length=8, prefix='x-', chars=(
        '-' + string.digits + string.ascii_uppercase + '_' +
        string.ascii_lowercase)):
    """Record IDs are random 48-bit RFC-4648 radix-64 with a fixed prefix
    to make them (somewhat) more human-recognizable

    First 15 bits are generated from Unix epoch to make them sortable
    by date (granularity 24 hours); rolls over after year 2107

    Args:
      length (int): length of generated portion after prefix
      prefix (str): prefix to distinguish ID type
      chars (str): set of characters to choose from for random portion
    """
    def _int2base(x, chars, base=64):
        return _int2base(x // base, chars, base).lstrip(chars[0]) + chars[
            x % base] if x else chars[0]
    return (prefix +
            _int2base((utcnow() - datetime(2018, 1, 1)).days * 8 +
                      random.randint(0, 8), chars, base=len(chars)) +
            ''.join(random.choice(chars) for i in range(length - 3)))


def req_duration():
    """Report request duration as milliseconds
    """
    return '%.3f' % (utcnow().timestamp() -
                     g.request_start_time.timestamp())


def utcnow():
    """For mocking: unittest.mock can't patch out datetime.utcnow directly """
    return datetime.utcnow()


def identity_normalize(identity):
    """Normalize an email address for use as an identity: downcase
    and in certain cases remove characters. This is required to secure
    against a type of attack involving password-resets: an example
    of the vulnerability is described here:
     https://jameshfisher.com/2018/04/07/the-dots-do-matter-how-to-scam-a-gmail-user/

    Args:
      identity (str): a raw email address
    Returns: str
    """
    if not identity:
        return
    if re.match('.*@gmail.com$', identity, re.I):
        identity = '%s@gmail.com' % identity.split('@')[0].replace('.', '')
    try:
        user, domain = identity.split('@')
        return ('%s@%s' % (user.split('+')[0], domain)).lower()
    except ValueError:
        return identity.lower()


def strip_tags(html):
    """Convert html to plain-text by stripping tags

    Args:
      html (str): an html document
    """
    s = HtmlStripper()
    s.feed(html)
    return s.get_data()


class HtmlStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []

    def handle_data(self, d):
        """ add a string to the html object

        Args:
          d (str): chunk of html
        """
        self.fed.append(d)

    def get_data(self):
        """ return the stripped html

        Returns: str
        """
        return ' '.join(self.fed)
