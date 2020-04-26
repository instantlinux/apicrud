## apicrud
[![](https://img.shields.io/pypi/v/apicrud.svg)](https://pypi.org/project/apicrud/) [![](https://images.microbadger.com/badges/image/instantlinux/example-api.svg)](https://microbadger.com/images/instantlinux/example-api "Image badge") [![](https://gitlab.com/instantlinux/apicrud/badges/master/pipeline.svg)](https://gitlab.com/instantlinux/apicrud/pipelines "pipelines") [![](https://gitlab.com/instantlinux/apicrud/badges/master/coverage.svg)](https://gitlab.com/instantlinux/apicrud/-/jobs/artifacts/master/file/apicrud/htmlcov/index.html?job=analysis "coverage")

### What is this

Skip the kubernetes / python / React.js learning curve and put your ideas in production!

The _apicrud_ framework was created to make it far easier to get started on full-stack development of REST-based services ranging from a simple CLI wrapper for queries of local APIs to full web-scale consumer-facing applications.

The essential components of a modern full-stack application include a back-end API server, a front-end UI server, a database, a memory-cache and a background worker for performing actions such as emailing, photo uploading or report generation. The challenge of setting up CI testing and microservice deployment is usually daunting; this repo addresses all of those issues by providing a fully-working example you can set up and start modifying in minutes. No prior experience is required.

This is the API back-end and worker, with an _example_ application.

### Usage

Clone this repo to your local environment. To start the example application in a shell session (on a Linux or Mac laptop):

* Set environment variables as defined below
* Install docker ([desktop for Mac](https://docs.docker.com/docker-for-mac/) or [Linux/Ubuntu](https://docs.docker.com/engine/install/ubuntu/) and enable kubernetes; if you're on a Mac install [homebrew](https://brew.sh); Linux _kubeadm_ setup is beyond scope of this README
* To run the full example demo in your local kubernetes:
  * Make secrets available: `ln -s example/secrets/.gnupg ~` if you don't already use gpg, or `make sops-import-gpg` if gpg is already installed
  * Invoke `TAG=latest make deploy_local`
  * Browse http://localhost:32180 as `admin` with password `p@ssw0rd` once all services are running
* Or, to run only database/cache images for developing on your laptop:
  * Invoke `make run_local` to bring up the back-end API with its dependent services mariadb, redis and rabbitmq
  * Invoke `make messaging_worker` to bring up the email/SMS worker back-end
  * Clone the [instantlinux/apicrud-ui](https://github.com/instantlinux/apicrud-ui) repo to a separate directory and follow the instructions given in its README to start and log into the front-end
* Optional: if setting up to run API within a docker container, configure kubernetes secrets as defined below (need at least the `example-db-password`)
* Optional for Linux: a full ansible-based bare-metal k8s cluster management suite is published at [instantlinux/docker-tools](https://github.com/instantlinux/docker-tools)

The example MVC application is provided here in this repo is also used as a fixture for its unit tests. You can fork / clone this repo and experiment with your own extensions to the database models, controller logic, and openapi.yaml REST endpoints. See [instantlinux/apicrud-ui](https://github.com/instantlinux/apicrud-ui) for definitions of the views (as React.js code).

### Environment variables

Variable | Default | Description
-------- | ------- | -----------
AMQ_HOST | `example-rmq` | IP address or hostname of rabbitMQ
API_DEV_PORT | `32080` | TCP port for API service (local dev k8s)
DB_HOST | `10.101.2.30` | IP address or hostname of MySQL-compatible database
DB_NAME | `example_local` | Name of the database
DB_PASS | `example` | Password for database
DOMAIN | | Domain for service URLs
EXAMPLE_API_PORT | `8080` | TCP port for API service
KUBECONFIG | | Config credentials filename for k8s
RABBITMQ_IP | `10.101.2.20` | IP address to use for rabbitMQ under k8s
REDIS_IP | `10.101.2.10` | IP address for redis under k8s

### Secrets

Kubernetes needs secrets defined. Default values for these are under example/secrets/. See the example/Makefile.sops (and the lengthy [kubernetes secrets doc](https://kubernetes.io/docs/concepts/configuration/secret/) for instructions on modifying them or adding new secrets for multiple namespace environments.

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
