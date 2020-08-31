#!/bin/sh -xe
export PYTHONPATH=/opt:$PYTHONPATH
sleep 10 && celery -A $CELERY_APP flower &
exec celery -A $CELERY_APP worker -Q ${QUEUE}_$APP_ENV \
     -n ${QUEUE}@%n --loglevel=INFO
