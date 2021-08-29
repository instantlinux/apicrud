# Getting Started

With a MacBook or Linux-based laptop, you can launch all the supported components with just a few commands.

### Usage

Clone this repo to your local environment. To start the example application in a shell session (on a Linux or Mac laptop):

* Install docker ([desktop for Mac](https://docs.docker.com/docker-for-mac/) or [Linux/Ubuntu](https://docs.docker.com/engine/install/ubuntu/)) and enable kubernetes; if you're on a Mac install [homebrew](https://brew.sh); Linux _kubeadm_ setup is beyond scope of this README
* Install helm: `sudo make helm_install`
* To run the full example demo in your local kubernetes:
    * Make secrets available: `ln -s example/secrets/.gnupg ~` if you don't already use gpg, or `make sops-import-gpg` if gpg is already installed
        * (If you've run through this once before and wiped your kubernetes configuration, run `make clean secrets`)
    * Invoke `TAG=latest make deploy_local` and wait for services to come up:
```
    $ kubectl get pods
    apicrud-backend-mariadb-0                 1/1     Running     0  9h
    apicrud-backend-redis-0                   1/1     Running     0  9h
    apicrud-backend-rmq-0                     1/1     Running     0  9h
    example-api-9d898b479-c52hs               1/1     Running     3  32h
    example-ui-7c9c99d89b-lk8pf               1/1     Running     0  21h
    example-worker-messaging-cdcc4bf96-5f97f  1/1     Running     0  32h
    $ kubectl get services
    apicrud-backend-mariadb ClusterIP      10.101.2.30      <none>   3306/TCP                    14d
    apicrud-backend-redis   ClusterIP      10.101.2.10      <none>   6379/TCP                    14d
    apicrud-backend-rmq     ClusterIP      10.101.2.20      <none>   4369/TCP,5671/TCP,5672/TCP  14d
    example-api        ClusterIP      10.101.2.2       <none>   8080/TCP                    8d
    example-dev-api    NodePort       10.97.75.110     <none>   8080:32080/TCP              8d
    example-dev-ui     NodePort       10.107.96.242    <none>   80:32180/TCP                8d
    example-ui         ClusterIP      None             <none>   80/TCP                      8d
    example-worker-messaging ClusterIP 10.98.233.206   <none>   5555/TCP                    13d
```
Note -- if you get a message like `IP is not in the valid range`, kubernetes will tell you the valid range; you can override the settings in example/values-local.yaml:
```
    db_host: 172.20.2.30
    ...
    api:
      service:
        clusterIP: 172.20.2.2
    ...
    redis:
      service:
        clusterIP: 172.20.2.10
    rmq:
      service:
        clusterIP: 172.20.2.20
```
    * Browse http://localhost:32180 as `admin` with password `p@ssw0rd`
* Or, to run only database/cache images for developing on your laptop:
    * Optional: set environment variables (as defined below) if you wish to override default values
    * Invoke `make apicrud-backend` to bring up the dependent services mariadb, redis and rabbitmq
    * Invoke `make run_local` to bring up the back-end API
    * Invoke `make messaging_worker` to bring up the email/SMS worker back-end
    * Clone the [instantlinux/apicrud-ui](https://github.com/instantlinux/apicrud-ui) repo to a separate directory and follow the instructions given in its README to start and log into the front-end
* Optional: configure outbound email (via GMail or another provider)
    * Head to [App Passwords](https://myaccount.google.com/apppasswords) account settings in your GMail account and generate an app password
    * Login as `admin` to the example demo UI (as above)
    * At upper right, go into Settings and choose Credentials tab
    * Add a new entry with name `gmail` and vendor `Google`: `key` is your GMail email address, `secret` is the app password
    * Choose Settings tab, set the smarthost to `smtp.gmail.com`, SMTP port to `587`, and select the SMTP credential you just created
    * Also in Settings tab, update the URL to match the hostname and port number you see in address bar
    * At upper right, go into Profile and select Contact Info
    * Edit the admin email address to your GMail address
* Optional: add the media service (requires AWS S3 or compatible service)
    * Invoke `TAG=latest make deploy_media` to bring up the media API and worker
    * Set up an S3 bucket in your AWS or compatible account
    * See usage instructions for [media service](https://github.com/instantlinux/apicrud-media#usage), starting with the `admin` login
    * Subsequent logins will now have access to media features in the UI
* Optional: if running API within a docker container, update the kubernetes secrets defined below; see instructions in [example/Makefile.sops](https://github.com/instantlinux/apicrud/blob/master/example/Makefile.sops)
* Prometheus metrics collector has a GUI on port 9090 of its container IP address
* Optional for Linux: a full ansible-based bare-metal k8s cluster management suite is published at [instantlinux/docker-tools](https://github.com/instantlinux/docker-tools)

The example MVC application provided here in this repo is also used as a fixture for its unit tests. You can fork / clone this repo and experiment with your own extensions to the database models, controller logic, and openapi.yaml REST endpoints. See [instantlinux/apicrud-ui](https://github.com/instantlinux/apicrud-ui) for definitions of the views (as React.js code).

### Environment variables

Variable | Default | Description
-------- | ------- | -----------
AMQ_HOST | `example-rmq` | IP address or hostname of rabbitMQ
API_DEV_PORT | `32080` | TCP port for API service (local dev k8s)
API_MEDIA_DEV_PORT | `32085` | TCP port for media API service (local dev k8s)
DB_HOST | `10.101.2.30` | IP address or hostname of MySQL-compatible database
DB_NAME | `example_local` | Name of the database
DOMAIN | | Domain for service URLs
EXAMPLE_API_PORT | `8080` | TCP port for API service
KUBECONFIG | | Config credentials filename for k8s
RABBITMQ_IP | `10.101.2.20` | IP address to use for rabbitMQ under k8s  
REDIS_IP | `10.101.2.10` | IP address for redis under k8s
UI_DEV_PORT | `32180` | TCP port for UI (local dev k8s)

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

All service instances for a given deployment must share the same db-aes and redis secrets. Rotating the redis secret simply requires relaunching all instances (which will invalidate current user sessions). Rotating the db-aes secret requires creating a migration script (which remains TODO).

### Single Sign On

Authentication via external providers such as Google, Twitter, GitHub, Facebook or others that provide centralized login compatible with OAuth2 ([RFC-6749](https://tools.ietf.org/html/rfc6749)) can often be a challenge to set up in a new application. Because this framework provides both the front-end and back-end implementation, most of the work has been done for you. Here are steps for making it work in your environment:

* Don't even try to begin setting up SSO without having your application running with a valid SSL certificate (served by an https URL). Details of doing that are beyond scope of this document; there are mechanisms such as cert-manager that automate this. To run a new service in your own environment this will be one of the first steps to prepare it for your users.

* Look in the [service_config.yaml](https://github.com/instantlinux/apicrud/blob/master/apicrud/service_config.yaml) defaults to see if auth_params for your provider are defined; you can add others but most of the major providers are pre-configured.

* When you request or reconfigure the provider's client, specify the "redirect URI" in the form `https://[your domain]/api/v1/auth_callback/[provider]`, such as `https://www.example.com/api/v1/auth_callback/google`.

* Get a client-id and client-secret from the provider. Google calls this an "application client ID"; other vendors may use different terminology. Some will issue these credentials directly from their developer-settings console screen; others may require submitting a form for approval.

* Add a secret containing the two values to your kubernetes installation.

* From the secret, define the environment variables `[vendor]_CLIENT_ID` and `[vendor]_CLIENT_SECRET` in the container's kubernetes deployment definition.

* Define the enviroment variable `AUTH_METHODS` as `local,oauth2`; the order determines which method will be tried first (local database or SSO).

* Once properly configured, you should see a `sign in with [vendor]` button on the login page.
