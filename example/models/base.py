"""Database model base

created 26-mar-2019 by richb@instantlinux.net

license: lgpl-2.1
"""

from sqlalchemy.ext.declarative import declarative_base

from apicrud import ServiceConfig

Base = declarative_base()
aes_secret = ServiceConfig().config.DB_AES_SECRET
