Customizing
===========

To define your own application, start with the example app. You can extend it by adding your own resource definitions. A resource will usually have a top-level path with standard CRUD endpoints in the REST API, with a model in the database and other logic implemented in controller and/or worker classes.

Checklist
=========

Here are items to add/modify for any new resource:

[ ] Component and path definitions in example/openapi/*.yaml 
[ ] Controller class and __init__
[ ] Model class(es)
[ ] Alembic version (database schema extensions)
[ ] Role permissions in rbac.yaml
[ ] Additions to config.yaml, if any
[ ] Any new grants (add to service_config.yaml, Grant schema in openapi.yaml)
[ ] Unit tests
[ ] Any new i18n text strings (backend often won't need changes)
[ ] Blank-database seed records, if any, in db_seed.yaml
