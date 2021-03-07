"""worker_processing.py

Media worker functions to process media
  Uploaded videos and photos contain metadata fields that we can parse
  and store in the database (plus the redis cache). Various sizes of
  images need to be sent to the storage API for quick retrieval; these
  functions are the background engine for such longer-running tasks.

created 3-feb-2020 by richb@instantlinux.net
"""

import celery
from datetime import datetime
import dateutil
import hashlib
import io
import logging
from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS

from ..account_settings import AccountSettings
from ..database import get_session
from ..exceptions import MediaUploadError
from ..grants import Grants
from ..service_config import ServiceConfig
from .storage import StorageAPI


class MediaProcessing(object):
    """Media Processing

    Attributes:
      uid (str): User ID
      file_id (str): ID of record in File model
      db_session (obj): database session
    """

    def __init__(self, uid, file_id, db_session=None):
        self.config = config = ServiceConfig().config
        self.models = ServiceConfig().models
        self.db_session = db_session or get_session(
            scopefunc=celery.utils.threads.get_ident, db_url=config.DB_URL)
        self.api = StorageAPI(uid=uid, db_session=self.db_session)
        self.file_id = file_id
        self.meta = self.api.get_file_meta(file_id)
        self.uid = uid

    def __del__(self):
        self.api.del_file_meta(self.file_id, self.meta)
        self.db_session.remove()

    def photo(self, meta):
        """metadata and scaling for still images

        Args:
          meta (dict): Image metadata
        """

        def _exif_get(field, max_width):
            if exif.get(field):
                return exif.get(field)[:max_width]

        # fetch the image
        suffix = "." + meta["ctype"]
        raw = self.api.get_object(meta["sid"], meta["path"] + suffix)
        if not raw:
            raise MediaUploadError("get_object failed for path=%s" %
                                   meta["path"])
        img = Image.open(io.BytesIO(raw))

        # parse its EXIF fields
        exif_raw = (hasattr(img, "_getexif") and img._getexif()) or {}
        exif = {TAGS[key]: val for key, val in exif_raw.items()
                if key in TAGS}
        geolat, geolong, altitude = None, None, None
        if exif.get("GPSInfo"):
            geolat, geolong, altitude = self._gpsexif(exif)
        date_orig = self._datetime(exif)

        # generate the 50-pixel thumbnail
        thumbnail = img.copy()
        thumbnail.thumbnail((self.config.THUMBNAIL_TINY,
                             self.config.THUMBNAIL_TINY), Image.ANTIALIAS)
        tbytes = io.BytesIO()
        thumbnail.save(tbytes, meta["ctype"])

        # construct and save a pictures db record
        modified = None
        try:
            if meta["modified"]:
                modified = datetime.strptime(meta["modified"],
                                             "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            logging.warn("action=photo message=invalid_date id=%s "
                         "modified=%s" % (meta["fid"], meta["modified"]))
        record = self.models.Picture(
            id=meta["fid"],
            name=meta["name"],
            path=meta["path"],
            uid=self.uid,
            category_id=AccountSettings(None, db_session=self.db_session,
                                        uid=meta["oid"]).get.category_id,
            compression=_exif_get("Compression", 16),
            datetime_original=date_orig or modified,
            format_original=meta["ctype"],
            geolat=geolat,
            geolong=geolong,
            gps_altitude=altitude,
            height=img.height,
            is_encrypted=False,
            make=_exif_get("Make", 16),
            model=_exif_get("Model", 32),
            orientation=exif.get("Orientation"),
            privacy=u"invitee",
            sha1=hashlib.sha1(raw).digest(),
            sha256=hashlib.sha256(raw).digest(),
            thumbnail50x50=tbytes.getvalue(),
            size=meta["size"],
            status="active",
            storage_id=meta["sid"],
            width=img.width,
        )
        self.db_session.add(record)
        # TODO remove
        self.db_session.commit()

        # add picture to album; first added is initial cover picture
        album = self.db_session.query(self.models.Album).filter_by(
            id=meta["pid"]).one()
        record = self.models.AlbumContent(
            album_id=meta["pid"],
            picture_id=meta["fid"],
            rank=len(album.pictures) + 1)
        self.db_session.add(record)
        if len(album.pictures) == 0 or album.cover_id is None:
            album.cover_id = meta["fid"]
            self.db_session.add(album)
        self.db_session.commit()

        # generate additional scaled sizes
        sizes = [int(x) for x in album.sizes.split(",")]
        for alt_size in sizes:
            if alt_size >= img.height:
                logging.info("skipping image name=%s resize=%d original=%d" %
                             (meta["name"], alt_size, img.height))
                continue
            width = int(img.width * alt_size / img.height)
            logging.info("generating image name=%s width=%d height=%d id=%s"
                         % (meta["name"], width, alt_size, meta["fid"]))
            alt_img = img.resize((width, alt_size), Image.ANTIALIAS)
            tbytes = io.BytesIO()
            alt_img.save(tbytes, meta["ctype"])
            if not self.api.put_object(
                    meta["sid"], "%s.%d%s" % (
                        meta["path"], alt_size, suffix),
                    tbytes.getvalue(),
                    content_type="image/%s" % meta["ctype"]):
                raise MediaUploadError("put_object failed")

        # stay in budget--throw away originals larger than max
        res_max = Grants(db_session=self.db_session).get('photo_res_max',
                                                         uid=self.uid)
        if img.height > res_max:
            self.api.del_object(meta["sid"], meta["path"] + suffix)

        # TODO (eventually)-apply encryption when gallery frontend has support
        #  and strip exif tags

    def video(self, meta):
        """metadata for videos - construct and save a pictures db record

        Args:
          meta (dict): Video metadata
        """
        # TODO decide whether to bother with exif or thumbnail

        modified = None
        try:
            if meta["modified"]:
                modified = datetime.strptime(meta["modified"],
                                             "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            logging.warn("action=video message=invalid_date id=%s "
                         "modified=%s" % (meta["fid"], meta["modified"]))
        # fetch the video, to calculate checksums
        suffix = "." + meta["ctype"]
        raw = self.api.get_object(meta["sid"], meta["path"] + suffix)
        if not raw:
            raise MediaUploadError("get_object failed for path=%s" %
                                   meta["path"])
        record = self.models.Picture(
            id=meta["fid"],
            name=meta["name"],
            path=meta["path"],
            uid=self.uid,
            category_id=AccountSettings(None, db_session=self.db_session,
                                        uid=meta["oid"]).get.category_id,
            compression=None,
            datetime_original=modified,
            duration=meta["duration"],
            format_original=meta["ctype"],
            geolat=None,
            geolong=None,
            gps_altitude=None,
            height=meta["height"],
            is_encrypted=False,
            make=None,
            model=None,
            orientation=None,
            privacy=u"invitee",
            sha1=hashlib.sha1(raw).digest(),
            sha256=hashlib.sha256(raw).digest(),
            thumbnail50x50=None,
            size=meta["size"],
            status="active",
            storage_id=meta["sid"],
            width=meta["width"],
        )
        self.db_session.add(record)

        # add to album
        album = self.db_session.query(self.models.Album).filter_by(
            id=meta["pid"]).one()
        # TODO query AlbumContents max(rank) to handle edge case
        record = self.models.AlbumContent(
            album_id=meta["pid"],
            picture_id=meta["fid"],
            rank=len(album.pictures) + 1)
        self.db_session.add(record)
        self.db_session.commit()

    def _gpsexif(self, exif):
        """Convert GPS exif data to fixed-decimal format. For some
        reason there"s no good standard python library for doing this.

        Args:
          exif (dict): the image's exif data
        Returns:
          tuple (lat, long, alt):
            first two are converted to fixed-precision int to fit in 32 bits
        """

        for item, val in GPSTAGS.items():
            if item in exif["GPSInfo"]:
                exif[val] = exif["GPSInfo"][item]

        # convert lat/long to fixed-precision 32-bit integers for SQL
        geolat, geolong, altitude = None, None, None
        if exif.get("GPSLatitude"):
            geolat = self._decimal_from_degrees(
                exif["GPSLatitude"], exif["GPSLatitudeRef"])
        if exif.get("GPSLongitude"):
            geolong = self._decimal_from_degrees(
                exif["GPSLongitude"], exif["GPSLongitudeRef"])
        if exif.get("GPSAltitude"):
            altitude = exif["GPSAltitude"][0] / exif["GPSAltitude"][1]
        return geolat, geolong, altitude

    def _datetime(self, exif):
        """Convert DateTimeOriginal exif data to python datetime.

        Args:
          exif (dict): the image's exif data
        Returns: datetime
        """
        date_orig = exif.get("DateTimeOriginal")
        if date_orig:
            try:
                # An old format with all colons
                return datetime.strptime(date_orig, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                pass
            try:
                ret = dateutil.parser.parse(date_orig)
            except ValueError:
                return None
            return ret

    @staticmethod
    def _decimal_from_degrees(dms, hemisphere):
        """
        Convert a DMS object to fixed-precision floating-point; we store
        geo coordinates with 7 digits of precision to fit in a 32-bit int.

        Args:
          dms (tuple): degrees / minutes / seconds
          hemisphere (str): N, S, E, W
        """
        degrees = int((dms[0] + dms[1] / 60.0 + dms[2] / 3600.0) * 1e7)
        if hemisphere in ("S", "W"):
            degrees = -degrees
        return degrees
