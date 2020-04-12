FROM instantlinux/python-wsgi:3.7.6-alpine3.11

MAINTAINER Rich Braun "richb@instantlinux.net"
ARG BUILD_DATE
ARG VCS_REF
ARG TAG
LABEL org.label-schema.build-date=$BUILD_DATE \
    org.label-schema.license=GPL-3.0 \
    org.label-schema.name=example-api \
    org.label-schema.vcs-ref=$VCS_REF \
    org.label-schema.vcs-url=https://github.com/instantlinux/apicrud
ENV AMQ_HOST=example-rmq \
    EXAMPLE_ENV=local

EXPOSE 8080
WORKDIR /opt/example
COPY requirements.txt uwsgi.ini /usr/src/
RUN pip3 install -r /usr/src/requirements.txt && \
    mkdir /var/opt/example && chown uwsgi /var/opt/example

COPY example/ /opt/example
RUN chmod -R g-w,o-w /opt/example && \
    ln -s /usr/lib/uwsgi/python3_plugin.so /opt/example/ && \
    sed -i -e "s/^vcs_ref =.*/vcs_ref = '$VCS_REF'/" \
    -e "s/^__version__ =.*/__version__ = '$TAG'/" \
    -e "s/^build_date =.*/build_date = '$BUILD_DATE'/" \
    /opt/example/_version.py
