## apicrud
[![](https://img.shields.io/pypi/v/apicrud.svg)](https://pypi.org/project/apicrud/) [![](https://images.microbadger.com/badges/version/instantlinux/apicrud.svg)](https://microbadger.com/images/instantlinux/apicrud "Version badge") [![](https://images.microbadger.com/badges/image/instantlinux/apicrud.svg)](https://microbadger.com/images/instantlinux/apicrud "Image badge") [![](https://images.microbadger.com/badges/commit/instantlinux/apicrud.svg)](https://microbadger.com/images/instantlinux/apicrud "Commit badge") [![](https://gitlab.com/instantlinux/apicrud/badges/master/pipeline.svg)](https://gitlab.com/instantlinux/apicrud/pipelines "pipelines") [![](https://gitlab.com/instantlinux/apicrud/badges/master/coverage.svg)](https://gitlab.com/instantlinux/apicrud/-/jobs/artifacts/master/file/junit.xml?job=analysis "coverage")

### What is this

Skip the python/React.js learning curve and put your ideas in production!

The _apicrud_ framework was created to make it far easier to get started on full-stack development of REST-based services ranging from a simple CLI wrapper for queries of local APIs to full web-scale consumer-facing applications.

The essential components of a modern full-stack application include a back-end API server, a front-end UI server, a database, a memory-cache and a background worker for performing actions such as emailing, photo uploading or report generation. This is the API back-end and worker, with an _example_ application.

### Usage

Clone this repo to your local environment. To start the example application in a shell session (on a Linux or Mac laptop):

* Set environment variables as defined below
* Install docker ([desktop for Mac](https://docs.docker.com/docker-for-mac/) or [Linux/Ubuntu](https://docs.docker.com/engine/install/ubuntu/) and enable kubernetes; Linux _kubeadm_ setup is beyond scope of this README
* Set up a local MariaDB or MySQL instance using _helm_ (TODO still beyond scope of
 this doc, the goal is to provide a single command that just-plain-works); create ablank database `example_local` and add a role user/password
* Invoke `make run_local` to bring up the back-end API with its dependent services redis and rabbitMQ
* Invoke `make messaging_worker` to bring up the email/SMS worker back-end
* Clone the [instantlinux/apicrud-ui](https://github/instantlinux/apicrud-ui) repo to a separate directory and follow the instructions given in its README to start the front-end
* Optional: if setting up to run API within a docker container, configure kubernetes secrets as defined below (need at least the `example-db-password`)
* Optional for Linux: a full ansible-based bare-metal k8s cluster management suite is published at [instantlinux/docker-tools](https://github.com/instantlinux/docker-tools)

The example MVC application is provided here in this repo is also used as a fixture for its unit tests. You can fork / clone this repo and experiment with your own extensions to the database models, controller logic, and openapi.yaml REST endpoints. See the instantlinux/apicrud-ui for definitions of the views (as React.js code).

### Environment variables

Variable | Default | Description
-------- | ------- | -----------
AMQ_HOST | `example-rmq` | IP address or hostname of rabbitMQ
DB_HOST | `db00` | IP address or hostname of MySQL-compatible database
DB_NAME | `example_local` | Name of the database
DB_PASS | | Password for database
DOMAIN | | Domain for service URLs
EXAMPLE_API_PORT | `8080` | TCP port for API service
KUBECONFIG | | Config credentials filename for k8s
RABBITMQ_IP | | IP address to use for rabbitMQ under k8s
REDIS_IP | | IP address for redis under k8s

TODO: the published docker image won't read these values at startup until the implementation of [env-config.js](https://www.freecodecamp.org/news/how-to-implement-runtime-environment-variables-with-create-react-app-docker-and-nginx-7f9d42a91d70/) is completed.

### Secrets

Kubernetes needs secrets defined. (TODO add default k8s yaml files and provide instructions here; [this](https://kubernetes.io/docs/concepts/configuration/secret/) is a ridiculously-steep learning curve for k8s rookies.)

Secret | Description
------ | -----------
example-db-aes-secret | Encryption passphrase for secured DB columns (~16 bytes)
example-db-password | Database password
example-flask-secret | Session passphrase (32 hex digits)
example-redis-secret | Encryption passphrase for redis values (~16 bytes)
mapquest-api-key | API key for address lookups (sign-up: [mapquest](http://developer.mapquest.com))

### Background

The rise of Docker and Kubernetes starting around 2017 made it possible to set up these production-grade services directly on the laptop of any developer. Only recently have the tools been easier to configure and set up. This framework provides working example code you can use to get started creating your own secure, web-scale services.

Implementation/design includes these technologies: <a href="http://www.celeryproject.org/">celery</a>, <a href="https://aws.amazon.com/cloudfront/">CloudFront and S3</a>, <a href="https://www.docker.com/">docker</a>, <a href="http://flask.pocoo.org/">flask</a>, <a href="https://kubernetes.io/">kubernetes</a>, <a href="https://developer.mapquest.com/documentation/open/geocoding-api/">MapQuest geocoding</a>, <a href="https://www.mapbox.com/">mapbox</a>, <a href="https://mariadb.org/">MariaDB</a>, <a href="https://docs.python.org/3/">python 3</a>, <a href="https://www.rabbitmq.com/">RabbitMQ</a>, <a href="https://reactjs.org">react.js</a>, <a href="https://marmelab.com/react-admin">react-admin</a>, <a href="https://www.sqlalchemy.org/">sqlalchemy</a>, <a href="https://uwsgi-docs.readthedocs.io/en/latest/">uWSGI</a>.

### Contributions

Your pull-requests and bug-reports are welcome here. See [CONTRIBUTING.md](CONTRIBUTING.md).

### License

Software copyright &copy; 2020 by Richard Braun &bull; <a href="https://www.apache.org/licenses/LICENSE-2.0">Apache 2.0</a> license <p />
