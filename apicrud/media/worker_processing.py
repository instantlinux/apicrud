"""worker_processing.py

Media worker functions to process media

created 3-feb-2020 by richb@instantlinux.net
"""

from datetime import datetime
import hashlib
import io
import logging
from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS

from ..account_settings import AccountSettings
from .storage import StorageAPI


class MediaUploadException(Exception):
    pass


class MediaProcessing(object):
    def __init__(self, uid, file_id, config, models, db_session=None):
        self.api = StorageAPI(redis_host=config.REDIS_HOST, uid=uid,
                              models=models, db_session=db_session)
        self.file_id = file_id
        self.config = config
        self.models = models
        self.meta = self.api.get_file_meta(file_id)

    def __del__(self):
        self.api.del_file_meta(self.file_id, self.meta)

    def photo(self, uid, meta, db_session):
        """metadata and scaling for still images
        """

        def _exif_get(field, max_width):
            if exif.get(field):
                return exif.get(field)[:max_width]

        # fetch the image
        suffix = "." + meta["ctype"]
        raw = self.api.get_object(meta["sid"], meta["path"] + suffix)
        if not raw:
            raise MediaUploadException("get_object failed for path=%s" %
                                       meta["path"])
        img = Image.open(io.BytesIO(raw))

        # parse its EXIF fields
        exif_raw = (hasattr(img, "_getexif") and img._getexif()) or {}
        exif = {TAGS[key]: val for key, val in exif_raw.items()
                if key in TAGS}
        geolat, geolong, altitude = None, None, None
        if exif.get("GPSInfo"):
            geolat, geolong, altitude = self._gpsexif(exif)

        # generate the 50-pixel thumbnail
        thumbnail = img.copy()
        thumbnail.thumbnail((self.config.THUMBNAIL_TINY,
                             self.config.THUMBNAIL_TINY), Image.ANTIALIAS)
        tbytes = io.BytesIO()
        thumbnail.save(tbytes, meta["ctype"])

        # construct and save a pictures db record
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
            uid=uid,
            category_id=AccountSettings(None, self.config, self.models,
                                        db_session=db_session,
                                        uid=meta["oid"]).get.category_id,
            compression=_exif_get("Compression", 16),
            datetime_original=exif.get("DateTimeOriginal") or modified,
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
        db_session.add(record)

        # add picture to album; first added is initial cover picture
        album = db_session.query(self.models.Album).filter_by(
            id=meta["pid"]).one()
        record = self.models.AlbumContent(
            album_id=meta["pid"],
            picture_id=meta["fid"],
            rank=len(album.pictures) + 1)
        db_session.add(record)
        if len(album.pictures) == 0 or album.cover_id is None:
            album.cover_id = meta["fid"]
            db_session.add(album)
        db_session.commit()

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
                raise MediaUploadException("put_object failed")

        # stay in budget--throw away originals larger than max
        # TODO grants needs to work under celery
        # res_max = Grants(db_session=db_session,
        #                  ttl=config.CACHE_TTL).get('photo_res_max')
        res_max = self.config.DEFAULT_GRANTS.get('photo_res_max')
        if img.height > res_max:
            self.api.del_object(meta["sid"], meta["path"] + suffix)

        # TODO (eventually)-apply encryption when gallery frontend has support
        #  and strip exif tags

    def video(self, uid, meta, db_session):
        """metadata for videos - construct and save a pictures db record"""

        # TODO decide whether to bother with exif or thumbnail

        try:
            if meta["modified"]:
                modified = datetime.strptime(meta["modified"],
                                             "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            logging.warn("action=video message=invalid_date id=%s "
                         "modified=%s" % (meta["fid"], meta["modified"]))
        record = self.models.Picture(
            id=meta["fid"],
            name=meta["name"],
            path=meta["path"],
            uid=uid,
            category_id=AccountSettings(None, self.config, self.models,
                                        db_session=db_session,
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
            sha1=None,
            sha256=None,
            thumbnail50x50=None,
            size=meta["size"],
            status="active",
            storage_id=meta["sid"],
            width=meta["width"],
        )
        db_session.add(record)

        # add to album
        album = db_session.query(self.models.Album).filter_by(
            id=meta["pid"]).one()
        # TODO query AlbumContents max(rank) to handle edge case
        record = self.models.AlbumContent(
            album_id=meta["pid"],
            picture_id=meta["fid"],
            rank=len(album.pictures) + 1)
        db_session.add(record)
        db_session.commit()

    def _gpsexif(self, exif):
        """Convert GPS exif data to fixed-decimal format. For some
        reason there"s no good standard python library for doing this.

        returns: tuple (lat, long, alt)
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

    @staticmethod
    def _decimal_from_degrees(dms, hemisphere):
        degrees = int((dms[0][0] / dms[0][1] +
                       dms[1][0] / dms[1][1] / 60.0 +
                       dms[2][0] / dms[2][1] / 3600.0) * 1e7)
        if hemisphere in ("S", "W"):
            degrees = -degrees
        return degrees
