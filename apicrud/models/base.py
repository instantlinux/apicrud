"""Database model base

created 26-mar-2019 by richb@instantlinux.net

license: lgpl-2.1
"""

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
aes_secret = None


def get_aes_secret():
    return aes_secret


class AsDictMixin(object):

    def as_dict(self):
        """Returns a serializable dict from an instance of the model

        Each table column is returned in the dict, except for any
        listed in a __rest_exclude__ tuple

        A list of related records' ids can be attached by defining
        one or more resource names in a __rest_related__ tuple
        """

        retval = self.__dict__.copy()
        if hasattr(self, '__rest_exclude__'):
            for col in self.__rest_exclude__:
                del(retval[col])
        if hasattr(self, '__rest_related__'):
            for key in self.__rest_related__:
                retval[key] = [rec.id for rec in getattr(self, key)]
        if hasattr(self, '__rest_hybrid__'):
            for key in self.__rest_hybrid__:
                retval[key] = getattr(self, key)
        retval.pop('_sa_instance_state', None)
        return retval
