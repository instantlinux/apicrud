## apicrud
[![](https://img.shields.io/pypi/v/apicrud.svg)](https://pypi.org/project/apicrud/) [![](https://images.microbadger.com/badges/image/instantlinux/example-api.svg)](https://microbadger.com/images/instantlinux/example-api "Image badge") [![](https://gitlab.com/instantlinux/apicrud/badges/master/pipeline.svg)](https://gitlab.com/instantlinux/apicrud/pipelines "pipelines") [![](https://gitlab.com/instantlinux/apicrud/badges/master/coverage.svg)](https://gitlab.com/instantlinux/apicrud/-/jobs/artifacts/master/file/apicrud/htmlcov/index.html?job=analysis "coverage")

### What is this

Skip the kubernetes / python / React.js learning curve and put your ideas in production!

The _apicrud_ framework makes it far easier to get started on full-stack development of REST-based services, ranging from a simple CLI wrapper for queries of local APIs to full web-scale consumer-facing applications running on kubernetes.

The essential components of a modern full-stack application include a back-end API server, a front-end UI server, a database, a memory-cache and a background worker for performing actions such as emailing, photo uploading or report generation. The challenge of setting up CI testing and microservice deployment is usually daunting; this repo addresses all of those issues by providing a fully-working example you can set up and start modifying in minutes. No prior experience is required.

This is the API back-end and worker, with an _example_ application.

### Usage

Clone this repo to your local environment. To start the example application in a shell session (on a Linux or Mac laptop):

* Install docker ([desktop for Mac](https://docs.docker.com/docker-for-mac/) or [Linux/Ubuntu](https://docs.docker.com/engine/install/ubuntu/)) and enable kubernetes; if you're on a Mac install [homebrew](https://brew.sh); Linux _kubeadm_ setup is beyond scope of this README
* To run the full example demo in your local kubernetes:
  * Make secrets available: `ln -s example/secrets/.gnupg ~` if you don't already use gpg, or `make sops-import-gpg` if gpg is already installed
  * Invoke `TAG=latest make deploy_local` and wait for services to come up:
    ```
    $ kubectl get pods
    example-api-9d898b479-c52hs               1/1     Running     3  32h
    example-mariadb-0                         1/1     Running     0  9h
    example-redis-f54fb554d-t4rtc             1/1     Running     0  14d
    example-rmq-0                             1/1     Running     0  14d
    example-ui-7c9c99d89b-lk8pf               1/1     Running     0  21h
    example-worker-messaging-cdcc4bf96-5f97f  1/1     Running     0  32h
    $ kubectl get services
    example-api        ClusterIP      10.101.2.2       <none>   8080/TCP                    8d
    example-dev-api    NodePort       10.97.75.110     <none>   8080:32080/TCP              8d
    example-dev-ui     NodePort       10.107.96.242    <none>   80:32180/TCP                8d
    example-mariadb    ClusterIP      10.101.2.30      <none>   3306/TCP                    14d
    example-redis      ClusterIP      10.101.2.10      <none>   6379/TCP                    14d
    example-rmq        ClusterIP      10.101.2.20      <none>   4369/TCP,5671/TCP,5672/TCP  14d
    example-ui         ClusterIP      None             <none>   80/TCP                      8d
    example-worker-messaging ClusterIP 10.98.233.206   <none>   5555/TCP                    13d
    ```
  * Browse http://localhost:32180 as `admin` with password `p@ssw0rd`
* Or, to run only database/cache images for developing on your laptop:
  * Optional: set environment variables (as defined below) if you wish to override default values
  * Invoke `make run_local` to bring up the back-end API with its dependent services mariadb, redis and rabbitmq
  * Invoke `make messaging_worker` to bring up the email/SMS worker back-end
  * Clone the [instantlinux/apicrud-ui](https://github.com/instantlinux/apicrud-ui) repo to a separate directory and follow the instructions given in its README to start and log into the front-end
* Optional: configure outbound email (via GMail or another provider)
  * Head to [App Passwords](https://myaccount.google.com/apppasswords) account settings in your GMail account and generate an app password
  * Login as `admin` to the example demo UI (as above)
  * At upper right, go into Settings and choose Credentials tab
  * Add a new entry: `key` is your GMail email address, `secret` is the app password
  * Choose Settings tab, set the smarthost to `smtp.gmail.com`, SMTP port to `587`, and select the SMTP credential you just created
  * Also in Settings tab, update the URL to match the hostname and port number you see in address bar
  * At upper right, go into Profile and select Contact Info
  * Edit the admin email address to your GMail address
* Optional: if running API within a docker container, update the kubernetes secrets defined below; see instructions in [example/Makefile.sops](https://github.com/instantlinux/apicrud/blob/master/example/Makefile.sops)
* Optional for Linux: a full ansible-based bare-metal k8s cluster management suite is published at [instantlinux/docker-tools](https://github.com/instantlinux/docker-tools)

The example MVC application provided here in this repo is also used as a fixture for its unit tests. You can fork / clone this repo and experiment with your own extensions to the database models, controller logic, and openapi.yaml REST endpoints. See [instantlinux/apicrud-ui](https://github.com/instantlinux/apicrud-ui) for definitions of the views (as React.js code).

### Environment variables

Variable | Default | Description
-------- | ------- | -----------
AMQ_HOST | `example-rmq` | IP address or hostname of rabbitMQ
API_DEV_PORT | `32080` | TCP port for API service (local dev k8s)
DB_HOST | `10.101.2.30` | IP address or hostname of MySQL-compatible database
DB_NAME | `example_local` | Name of the database
DOMAIN | | Domain for service URLs
EXAMPLE_API_PORT | `8080` | TCP port for API service
KUBECONFIG | | Config credentials filename for k8s
RABBITMQ_IP | `10.101.2.20` | IP address to use for rabbitMQ under k8s
REDIS_IP | `10.101.2.10` | IP address for redis under k8s

### Secrets

Kubernetes needs secrets defined. Default values for these are under example/secrets/. See the [example/Makefile.sops](https://github.com/instantlinux/apicrud/blob/master/example/Makefile.sops) (and the lengthy [kubernetes secrets doc](https://kubernetes.io/docs/concepts/configuration/secret/) for instructions on modifying them or adding new secrets for multiple namespace environments.

Secret | Description
------ | -----------
example-db-aes-secret | Encryption passphrase for secured DB columns (~16 bytes)
example-db-password | Database password
example-flask-secret | Session passphrase (32 hex digits)
example-redis-secret | Encryption passphrase for redis values (~16 bytes)
mapquest-api-key | API key for address lookups (sign-up: [mapquest](http://developer.mapquest.com))
mariadb-root-password | Root password for MariaDB

### Background

The rise of Docker and Kubernetes starting around 2017 made it possible to set up these production-grade services directly on the laptop of any developer. Only recently have the tools been easier to configure and set up. This framework provides working example code you can use to get started creating your own secure, web-scale services.

Implementation/design includes these technologies: [celery](http://www.celeryproject.org/), [CloudFront and S3](https://aws.amazon.com/cloudfront/), [docker](https://www.docker.com/), [flask](http://flask.pocoo.org/), [kubernetes](https://kubernetes.io/), [MapQuest geocoding](https://developer.mapquest.com/documentation/open/geocoding-api/), [mapbox](https://www.mapbox.com/), [MariaDB](https://mariadb.org/), [python 3](https://docs.python.org/3/), [OpenAPI](https://www.openapis.org/), [RabbitMQ](https://www.rabbitmq.com/), [react.js](https://reactjs.org/), [react-admin](https://marmelab.com/react-admin), [redis](https://redis.io/), [sqlalchemy](https://www.sqlalchemy.org/), [uWSGI](https://uwsgi-docs.readthedocs.io/en/latest/).

### Contributions

Your pull-requests and bug-reports are welcome here. See [CONTRIBUTING.md](CONTRIBUTING.md).

### License

Software copyright &copy; 2020 by Richard Braun &bull; <a href="https://www.apache.org/licenses/LICENSE-2.0">Apache 2.0</a> license <p />
