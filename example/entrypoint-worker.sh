#!/bin/sh -xe
sleep 10 && celery -A $CELERY_APP flower &
exec celery -A $CELERY_APP worker -Q ${QUEUE}_$EXAMPLE_ENV \
     -n ${QUEUE}@%n --loglevel=INFO
