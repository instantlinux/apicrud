# Your Project's Lifecycle

TODO - this portion is incomplete

## Iterating on features
Each feature will likely require the following:

* A schema definition in `models.py`
* Schema and endpoint definitions in `openapi.yaml`
* Controller class inherited from `BasicCRUD` with initialization in controllers.__init__
* Permissions defined in `rbac.yaml`
* Unit / functional tests
* Docstrings and potentially updates to the user doc

Some features may need additional settings added to `config.py` or background processing in `messaging.py`, the media service or a new microservice worker.

## Peer review

If you're working with a team, host your git repository on GitHub, GitLab or an internal git server. If you're using GitHub, add a Pull Request template to the repo as .github/PULL_REQUEST_TEMPLATE.md (this repo has an example) and make a checklist for your team members to use as they confirm one another's work. Make a separate branch for each feature or bugfix, and follow the Git Flow model (or rival approaches such as [this suggestion](https://about.gitlab.com/blog/2020/03/05/what-is-gitlab-flow/) from a GitLab user). Once a Pull Request (known as a Merge Request in the GitLab community) is finalized, the branch is merged to master, then deleted and the release engineering steps can proceed.

## Release engineering

## Choosing your online vendors

For hosting an open-source application, you'll want to set up these accounts; many other services are available for closed-source / commercial applications. Each of these services has a no-cost tier of indefinite duration except for those marked with a $ symbol.

Purpose | Vendor options
------- | --------------
Code repo | [GitHub](https://github.com), [GitLab](https://gitlab.com)
CDN | [Cloudflare](https://www.cloudflare.com/), $ [AWS Cloudfront](https://aws.amazon.com/cloudfront/)
CI/CD | [Gitlab-CI](https://about.gitlab.com/solutions/github/), many alternatives
DNS | [Cloudflare](https://www.cloudflare.com/), $ UltraDNS, $ EasyDNS, several others
Docs | [Read the Docs](https://readthedocs.org/accounts/signup/)
Geocoding | [Mapquest](https://developer.mapquest.com/documentation/geocoding-api/)
Javascript repo | [npmjs](https://npmjs.com)
Maps | [Mapbox](https://www.mapbox.com/signup/)
Outbound mail | [GMail](https://mail.google.com), many alternatives
Python repo | [PyPI](https://pypi.org)
Registry | [Docker Hub](https://hub.docker.com/)
Storage | $ [AWS S3](https://aws.amazon.com/account/), $ [Backblaze B2](https://www.backblaze.com/)

## Logging and troubleshooting

## Supporting your users

