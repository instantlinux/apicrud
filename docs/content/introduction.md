# Introduction

Skip the kubernetes / python / React.js learning curve and put your ideas in production!

The _APIcrud_ framework makes it easier to get started on full-stack development of REST-based services, ranging from a simple CLI wrapper for queries of local APIs to full web-scale consumer-facing applications running on kubernetes.

The essential components of a modern full-stack application include a back-end API server, a front-end UI server, a database, a memory-cache and a background worker for performing actions such as emailing, photo uploading or report generation. The challenge of setting up CI testing and microservice deployment is usually daunting; this repo addresses all of those issues by providing a fully-working example you can set up and start modifying in minutes. No prior experience is required.

## Features

Out of the box, here are some of the capabilities included in the example application:

* User-account setup, following standard security practices with password lockout and reset via email
* Encryption-at-rest for credentials
* Microservice discovery
* GeoIP location lookup and map display
* Customizable per-account grant limits (such as list size, number of contacts)
* User-profile and settings screens
* Extensible internationalization support
* Photo and file uploads, with a mobile-friendly photo album
* Configurable role-based access control for all resource types, with per-object privacy settings
* Storage and content-delivery support for AWS
* Messaging via email and SMS
* Scalability and fault-tolerance for all services

## About the Name

APIcrud is based on the [OpenAPI 3.0](https://en.wikipedia.org/wiki/OpenAPI_Specification) standard for RESTful web services. While newer APIs have been developed, such as gRPC (Google) and GraphQL (Facebook), REST remains by far the most widely supported and easiest to learn interface for getting your software deployed.

## Technology Stack

This system is built with the following technologies: [babel](http://babel.pocoo.org/en/latest/), [celery](http://www.celeryproject.org/), [CloudFront and S3](https://aws.amazon.com/cloudfront/), [docker](https://www.docker.com/), [flask](http://flask.pocoo.org/), [kubernetes](https://kubernetes.io/), [MapQuest geocoding](https://developer.mapquest.com/documentation/open/geocoding-api/), [mapbox](https://www.mapbox.com/), [MariaDB](https://mariadb.org/), [python 3](https://docs.python.org/3/), [RabbitMQ](https://www.rabbitmq.com/), [react.js](https://reactjs.org), [react-admin](https://marmelab.com/react-admin), [sqlalchemy](https://www.sqlalchemy.org/), [uWSGI](https://uwsgi-docs.readthedocs.io/en/latest/).

## License

Software copyright &copy; 2020 by Richard Braun &bull; [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0)
