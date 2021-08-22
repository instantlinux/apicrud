Example Application
===================
This example serves a simple message-board. The `source code <https://github.com/instantlinux/apicrud/tree/master/example>`_ provides all the files needed to launch the service into a kubernetes cluster.


.. code-block::

    example
    ├── alembic.ini              # alembic settings
    ├── celeryconfig.py          # celery-worker parameters
    ├── config.yaml              # application settings
    ├── constants.py             # global constants
    ├── db_seed.yaml             # db initial seed records
    ├── Dockerfile.api           # container image builder scripts
    ├── Dockerfile.worker
    ├── entrypoint-worker.sh     # container startup script
    ├── i18n                     # application language translations
    │   ├── messages.pot         # extracted language strings
    │   ├── ar                   # arabic message mappings
    │   └── de (...)             # german messages (and so on)
    ├── main.py                  # top-level startup
    ├── Makefile.dev             # administrative utilities
    ├── Makefile.i18n
    ├── Makefile.k8s
    ├── Makefile.sops
    ├── Makefile.vars
    ├── messaging.py             # messaging worker startup
    ├── models
    │   ├── __init__.py          # models for database schema
    │   ├── api.py               # open-core API models
    │   ├── base.py              # declarative base
    │   └── ...                  # add your custom models here
    ├── openapi                  # OpenAPI 3.0 specifications
    │   ├── api.yaml             # top-level API spec
    │   ├── account.schema.yaml  # open-core API model schema
    │   ├── account.path.yaml    # open-core API routing paths
    │   └── ...                  # add your custom specs here
    ├── rbac.yaml                # endpoint permissions
    ├── requirements.txt         # python dependencies
    ├── uwsgi.ini                # UWSGI server settings
    ├── _version.py              # application version
    ├── alembic                  # schema upgrade instructions
    │   ├── env.py
    │   └── versions
    │       ├── xxx_schema1.py
    │       └── xxx_schema2.py
    ├── controllers              # controller classes
    │   ├── __init__.py          # controller initialization
    │   ├── ...
    │   ├── list.py
    │   ├── message.py
    │   ├── ...
    │   └── tz.py
    ├── helm                     # kubernetes helm charts
    │   ├── apicrud-backend
    │   │   └── subcharts
    │   │       ├── mariadb
    │   │       ├── prometheus
    │   │       ├── redis
    │   │       └── rmq
    │   ├── example-api
    │   │   └── subcharts
    │   │       ├── api
    │   │       └── media
    │   ├── example-ui
    │   │   └── subcharts
    │   │       └── ui
    │   └── example-worker
    │       └── subcharts
    │           └── worker
    └── secrets                  # credentials used at runtime

.. currentmodule:: example
.. automodule:: example
    :members:

.. autosummary::
     :toctree: stubs
     :recursive:

     constants
     controllers
     main
     messaging
     models
