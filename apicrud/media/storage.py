"""storage.py

Storage access

created 25-jan-2020 by richb@instantlinux.net
"""

from b2sdk.v1 import B2Api, InMemoryAccountInfo
import base64
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from datetime import datetime
from flask import g
import json
import logging
import re
import redis
from sqlalchemy.orm.exc import NoResultFound
import uuid

import apicrud.access as access
import apicrud.constants as constants
import apicrud.grants as grants
import apicrud.utils as utils


class StorageAPI(object):

    def __init__(self, credential_ttl=None, redis_conn=None, redis_host=None,
                 redis_port=6379, cache_ttl=1200, uid=None, models=None,
                 db_session=None):
        self.models = models
        self.redis_conn = (
            redis_conn or redis.Redis(host=redis_host, port=redis_port, db=0))
        self.cache_ttl = cache_ttl
        self.credential_ttl = credential_ttl or 86400
        self.uid = uid or access.AccessControl().uid
        self.db = db_session or g.db

    def get_upload_url(self, body):
        storage_id = body.get('storage_id')
        try:
            storage = self.db.query(self.models.Storage).filter_by(
                id=storage_id, status='active').one()
        except NoResultFound:
            return dict(id=storage_id, message='storage volume not found'), 404
        resource = body.get('parent_type', 'album')
        if re.compile('^[a-f0-9]{8}-?[a-f0-9]{4}-?4[a-f0-9]{3}'
                      '-?[89ab][a-f0-9]{3}-?[a-f0-9]{12}.jpeg').match(
                          body.get('name').lower()):
            # Make iPhone filename shorter
            body['name'] = base64.urlsafe_b64encode(
                uuid.UUID(body['name'].strip('.jpeg')).bytes).rstrip(
                    b'=').decode('ascii') + '.jpeg'
        logmsg = dict(uid=self.uid, resource=resource, name=body.get('name'),
                      size=body.get('size'))

        model = dict(album=self.models.Album, list=self.models.List,
                     message=self.models.Message)[resource]
        if resource == 'album':
            try:
                record = self.db.query(model).filter_by(
                    id=body.get('parent_id'), status='active')
                album_size = len(record.one().pictures)
            except NoResultFound:
                return dict(album_id=body.get(
                    'parent_id'), message='album not found'), 404
            max_size = grants.Grants(self.models,
                                     db_session=self.db,
                                     ttl=self.cache_ttl).get('album_size')
            if album_size >= max_size:
                msg = 'album is full (max=%d)' % max_size
                logging.info(dict(message=msg, **logmsg))
                return dict(message=msg), 405
        if not access.AccessControl(
                models=self.models, model=model).with_permission(
                    'u', query=record):
            msg = 'access_denied'
            logging.warning(dict(message=msg, **logmsg))
            return dict(message='access denied'), 403

        self.vendor = storage.credentials.vendor
        id = utils.gen_id(prefix='f-')
        if body.get('content_type'):
            ctype = body['content_type'].split('/')[1]
        else:
            ctype = None
        storage_path = ('%s/%s/%s' % (
            storage.prefix if storage.prefix else '', self.uid, id)).strip('/')
        suffix = '.' + ctype if ctype else ''
        if ctype in constants.MIME_VIDEO_TYPES:
            duration_max = grants.Grants(
                self.models, db_session=self.db,
                ttl=self.cache_ttl).get('video_duration_max')
            if body.get('duration') and body['duration'] > duration_max:
                msg = 'video exceeds maximum duration=%f' % duration_max
                logging.warning(dict(message=msg, **logmsg))
                return dict(message=msg), 405
        max_size = grants.Grants(
            self.models, db_session=self.db,
            ttl=self.cache_ttl).get('media_size_max')
        if body.get('size') and body['size'] > max_size:
            msg = 'file size exceeds max=%d' % max_size
            logging.info(dict(message=msg, **logmsg))
            return dict(message=msg), 405
        if self.vendor == 'backblaze':
            result, status = StorageBackblaze(
                self.models.Storage).get_upload_url(
                    storage_id, storage_path + suffix,
                    content_type=body.get('content_type'))
        elif self.vendor == 'aws':
            result, status = StorageS3(
                credentials=storage.credentials,
                credential_ttl=self.credential_ttl).get_upload_url(
                    storage.bucket, storage_path + suffix,
                    content_type=body.get('content_type'))
        else:
            return dict(message='Unsupported vendor=%s' % self.vendor), 405
        if status != 201:
            return result, status
        meta = dict(
            created=g.request_start_time.timestamp(),
            ctype=ctype,
            duration=body.get('duration'),
            fid=id,
            height=body.get('height'),
            modified=body.get('modified'),
            name=body.get('name'),
            oid=storage.uid,
            path=storage_path,
            pid=body.get('parent_id'),
            sid=storage_id,
            size=body.get('size'),
            uid=self.uid,
            width=body.get('width'))
        self.update_file_meta(id, meta)
        logging.info(dict(action='get_upload_url', **logmsg))
        return dict(params=result['fields'], upload_url=result['uploadUrl'],
                    file_id=id), status

    def get_file_meta(self, file_id):
        """
        returns:
        dict with fid, uid, sid, pid, path, name
        """
        key = 'fid:%s:%s' % (self.uid, file_id[-8:])
        try:
            meta = json.loads(self.redis_conn.get(key))
        except TypeError:
            return None
        except Exception as ex:
            logging.warn('action=get_upload_state uid=%s exception=%s' %
                         (self.uid, str(ex)))
            return None
        return meta

    def update_file_meta(self, file_id, meta):
        key = 'fid:%s:%s' % (self.uid, file_id[-8:])
        try:
            self.redis_conn.set(key, json.dumps(meta), ex=self.cache_ttl,
                                nx=True)
        except Exception as ex:
            logging.warn('action=update_file_meta uid=%s exception=%s' %
                         (self.uid, str(ex)))

    def del_file_meta(self, file_id, meta):
        key = 'fid:%s:%s' % (self.uid, file_id[-8:])
        try:
            self.redis_conn.delete(key)
        except Exception as ex:
            logging.warn('action=del_file_meta uid=%s exception=%s' %
                         (self.uid, str(ex)))

    def upload_complete(self, file_id, status, func_worker):
        """ Finalize upload - pass to the worker

        params:
          file_id - ID of file meta in redis
          status - completion status from frontend ('done' if OK)
          func_worker - callback function for passing to celery worker
        """

        meta = self.get_file_meta(file_id)
        if meta and status == 'done':
            duration = datetime.utcnow().timestamp() - meta['created']
            logging.info(dict(action='upload_complete', file_id=file_id,
                              duration='%.3f' % duration))
            func_worker(self.uid, file_id)
            return dict(file_id=file_id), 201
        else:
            msg = 'unhandled frontend status'
            logging.warning('action=upload_complete status=%s message=%s' %
                            (status, msg))
            return dict(file_id=file_id, message=msg), 405

    def fetch_album_meta(self, album_id, thumbnail_height):
        """Retrieve metadata of a media album in format suitable
        for react-image-gallery
        """

        album = self.db.query(self.models.Album).filter(
            self.models.Album.id == album_id,
            self.models.Picture.status == 'active').one()
        results = []
        for picture in album.pictures:
            orig_uri = None
            uri_path = '%s/%s' % (picture.storage.cdn_uri, picture.path)
            fmt = picture.format_original
            sizes = [int(x) for x in album.sizes.split(',')
                     if not picture.height or int(x) <= picture.height]
            if fmt in constants.MIME_VIDEO_TYPES:
                # TODO see line 249 of xiaolin's app.js example
                logging.warning('resource=album action=get id=%s '
                                'message=videos_nyi' % picture.id)
                continue
            else:
                max_height = grants.Grants(
                    self.models, self.db,
                    ttl=self.cache_ttl).get('photo_res_max')
                if not picture.height or picture.height <= max_height:
                    orig_uri = '%s.%s' % (uri_path, fmt)
                else:
                    orig_uri = '%s.%d.%s' % (uri_path, max_height, fmt)
            results.append(dict(
                id=picture.id,
                description=picture.caption,
                duration=picture.duration,
                height=picture.height,
                imageSet=[dict(srcSet='%s.%d.%s' % (uri_path, res, fmt),
                               media='(max-width: %dpx)' % res) for
                          res in sizes],
                name=picture.name,
                original=orig_uri,
                path=picture.path,
                size=picture.size,
                thumbnail='%s.%d.%s' % (uri_path, thumbnail_height, fmt),
                type='%s/%s' % ('video' if fmt in constants.MIME_VIDEO_TYPES
                                else 'image', fmt),
                uid=picture.uid,
                width=picture.width))
            if picture.height and picture.height <= max_height:
                results[-1]['imageSet'].append(dict(
                    srcSet='%s.%s' % (uri_path, fmt),
                    media='(max-width: %dpx)' % picture.height))
                results[-1]['imageSet'].append(dict(
                    srcSet='%s.%s' % (uri_path, fmt),
                    media='(min-width: %dpx)' % picture.height))
            else:
                results[-1]['imageSet'].append(dict(
                    srcSet='%s.%d.%s' % (uri_path, sizes[-1], fmt),
                    media='(min-width: %dpx)' % sizes[-1]))
        return results

    def get_object(self, storage_id, storage_key):
        try:
            storage = self.db.query(self.models.Storage).filter_by(
                id=storage_id, status='active').one()
        except NoResultFound:
            logging.error('storage volume not found')
        if storage.credentials.vendor == 'aws':
            return StorageS3(credentials=storage.credentials).get_object(
                                 storage.bucket, storage_key)

    def put_object(self, storage_id, storage_key, content,
                   content_type='image/jpeg'):
        try:
            storage = self.db.query(self.models.Storage).filter_by(
                id=storage_id, status='active').one()
        except NoResultFound:
            logging.error('storage volume not found')
        if storage.credentials.vendor == 'aws':
            return StorageS3(credentials=storage.credentials).put_object(
                                 storage.bucket, storage_key, content,
                                 content_type=content_type)

    def del_object(self, storage_id, storage_key):
        try:
            storage = self.db.query(self.models.Storage).filter_by(
                id=storage_id, status='active').one()
        except NoResultFound:
            logging.error('storage volume not found')
        if storage.credentials.vendor == 'aws':
            return StorageS3(credentials=storage.credentials).del_object(
                                 storage.bucket, storage_key)


class StorageBackblaze(object):

    def __init__(self, model, db_session=None):
        self.api = B2Api(InMemoryAccountInfo())
        self.db = db_session
        self.model = model

    def get_upload_url(self, storage_id, storage_key,
                       content_type='image/jpeg'):
        try:
            storage = self.db.query(self.model).filter_by(
                id=storage_id, status='active').one()
        except NoResultFound:
            return dict(id=storage_id, message='storage volume not found'), 404

        self.api.authorize_account(
            'production', storage.credentials.key, storage.credentials.secret)
        try:
            result = self.api.raw_api.get_upload_url(
                self.api.account_info.get_api_url(),
                self.api.account_info.get_account_auth_token(),
                storage.identifier)
        except Exception as ex:
            msg = str(ex)
            return dict(message=msg, id=storage_id), 405
        return result, 201


class StorageS3(object):

    def __init__(self, credential_ttl=3600, credentials=None, access_key=None,
                 secret_key=None, region=constants.DEFAULT_AWS_REGION):
        self.credential_ttl = credential_ttl
        self.region = region
        if credentials:
            self.access_key = credentials.key
            self.secret_key = credentials.secret
        else:
            self.access_key = access_key
            self.secret_key = secret_key
        self.api = boto3.client(
            's3', aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            # signature_version = 's3v4',
            config=Config(s3={'addressing_style': 'virtual'}))

    def get_upload_url(self, bucket, storage_key,
                       content_type='image/jpeg'):
        try:
            result = self.api.generate_presigned_post(
                bucket, storage_key, ExpiresIn=self.credential_ttl)
        except ClientError as ex:
            msg = str(ex)
            return dict(message=msg, bucket=bucket), 405
        return dict(fields=result['fields'], uploadUrl=result['url']), 201

    def get_object(self, bucket, storage_key):
        """Fetch the object into a byte array"""

        return self.api.get_object(Bucket=bucket,
                                   Key=storage_key)['Body'].read()

    def put_object(self, bucket, storage_key, content,
                   content_type='image/jpeg'):
        """Store a byte-array object"""

        logging.debug(dict(action='put', bucket=bucket,
                           storage_key=storage_key, content_type=content_type))
        return self.api.put_object(
            Bucket=bucket, Key=storage_key, Body=content,
            ContentType=content_type)

    def del_object(self, bucket, storage_key):
        """Delete an object"""

        logging.debug(dict(action='del', bucket=bucket,
                           storage_key=storage_key))
        return self.api.delete_object(Bucket=bucket, Key=storage_key)