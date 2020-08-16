Example Application
===================
This example serves a simple message-board. The `source code <https://github.com/instantlinux/apicrud/tree/master/example>`_ provides all the files needed to launch the service into a kubernetes cluster.


.. code-block::

    example
    ├── alembic.ini              # alembic settings
    ├── celeryconfig.py          # celery-worker parameters
    ├── config.yaml              # application settings
    ├── constants.py             # global constants
    ├── db_schema.py             # db initial seed/update functions
    ├── Dockerfile.api           # container image builder scripts
    ├── Dockerfile.worker
    ├── entrypoint-worker.sh     # container startup script
    ├── i18n_textstrings.py      # application language translations
    ├── main.py                  # top-level startup
    ├── Makefile.dev             # administrative utilities
    ├── Makefile.k8s
    ├── Makefile.sops
    ├── Makefile.vars
    ├── messaging.py             # messaging worker startup
    ├── models.py                # models for database schema
    ├── openapi.yaml             # OpenAPI 3.0 specifications
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
    │   ├── account.py
    │   ├── auth.py
    │   ├── category.py
    │   ├── contact.py
    │   ├── credential.py
    │   ├── grant.py
    │   ├── health.py
    │   ├── list.py
    │   ├── location.py
    │   ├── message.py
    │   ├── person.py
    │   ├── settings.py
    │   └── tz.py
    ├── k8s                      # kubernetes resource specifications
    │   ├── api.yaml
    │   ├── dev.yaml
    │   ├── mariadb.yaml
    │   ├── media-worker.yaml
    │   ├── media.yaml
    │   ├── prod.yaml
    │   ├── redis.yaml
    │   ├── rmq.yaml
    │   ├── ui.yaml
    │   └── worker.yaml
    └── secrets                  # credentials used at runtime

.. currentmodule:: example
.. automodule:: example
    :members:

.. autosummary::
     :toctree: stubs
     :recursive:

     config
     constants
     controllers
     db_schema
     i18n_textstrings
     main
     messaging
     models
