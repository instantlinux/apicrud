## apicrud
[![](https://img.shields.io/pypi/v/apicrud.svg)](https://pypi.org/project/apicrud/) [![](https://images.microbadger.com/badges/image/instantlinux/example-api.svg)](https://microbadger.com/images/instantlinux/example-api "Image badge") [![](https://gitlab.com/instantlinux/apicrud/badges/master/pipeline.svg)](https://gitlab.com/instantlinux/apicrud/pipelines "pipelines") [![](https://gitlab.com/instantlinux/apicrud/badges/master/coverage.svg)](https://gitlab.com/instantlinux/apicrud/-/jobs/artifacts/master/file/apicrud/htmlcov/index.html?job=analysis "coverage") ![](https://img.shields.io/badge/platform-amd64%20arm64%20arm%2Fv6%20arm%2Fv7-blue "Platform badge") [![](https://img.shields.io/badge/dockerfile-latest-blue)](https://gitlab.com/instantlinux/apicrud/-/blob/master/example/Dockerfile.api "dockerfile")

### What is this

Skip the kubernetes / python / React.js learning curve and put your ideas in production!

The _APIcrud_ framework makes it easier to get started on full-stack development of REST-based services, ranging from a simple CLI wrapper for queries of local APIs to full web-scale consumer-facing applications running on kubernetes.

The essential components of a modern full-stack application include a back-end API server, a front-end UI server, a database, a memory-cache and a background worker for performing actions such as emailing, photo uploading or report generation. The challenge of setting up CI testing and microservice deployment is usually daunting; this repo addresses all of those issues by providing a fully-working example you can set up and start modifying in minutes. No prior experience is required.

This is the API back-end and worker, with an _example_ application.

### Usage

See the [getting started](docs/content/gettingstarted.md) page, or navigate to [Read the Docs](https://apicrud.readthedocs.io/).

### Background

The rise of Docker and Kubernetes starting around 2017 made it possible to set up these production-grade services directly on the laptop of any developer. Only recently have the tools been easier to configure and set up. This framework provides working example code you can use to get started creating your own secure, web-scale services.

Implementation/design includes these technologies: [babel](http://babel.pocoo.org/en/latest/), [celery](http://www.celeryproject.org/), [CloudFront and S3](https://aws.amazon.com/cloudfront/), [docker](https://www.docker.com/), [flask](http://flask.pocoo.org/), [kubernetes](https://kubernetes.io/), [MapQuest geocoding](https://developer.mapquest.com/documentation/open/geocoding-api/), [mapbox](https://www.mapbox.com/), [MariaDB](https://mariadb.org/), [python 3](https://docs.python.org/3/), [OpenAPI](https://www.openapis.org/), [RabbitMQ](https://www.rabbitmq.com/), [react.js](https://reactjs.org/), [react-admin](https://marmelab.com/react-admin), [redis](https://redis.io/), [sqlalchemy](https://www.sqlalchemy.org/), [uWSGI](https://uwsgi-docs.readthedocs.io/en/latest/).

### Contributions

Your pull-requests and bug-reports are welcome here. See [CONTRIBUTING.md](CONTRIBUTING.md).

### License

Software copyright &copy; 2020 by Richard Braun &bull; <a href="https://www.apache.org/licenses/LICENSE-2.0">Apache 2.0</a> license <p />
