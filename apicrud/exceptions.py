"""exceptions.py

created 21-jan-2021 by richb@instantlinux.net
"""


class APIcrudException(Exception):
    pass


class APIcrudFormatError(APIcrudException):
    pass


class APIcrudSendError(APIcrudException):
    pass


class MediaUploadError(Exception):
    pass
