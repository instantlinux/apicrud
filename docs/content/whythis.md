Why This Project?
=================

There are lots of developer frameworks in the history of computing, so two questions you'll have when considering yet another one are:

* Why would I choose this one?
* Why on Earth did it get created, anyway?

## What to Consider

If you're thinking of using this framework, here are questions to ask as you consider ruling this one or alternatives out (or in):

* How hard is it to master?
* Am I starting a new project or adapting an old one?
* How quickly can I get a demo up and running?
* Does it have full customizability to handle my unique requirements?
* Does it have the performance that I need?
* Does using it reduce complexity of the workflow for me and my team?
* Do the tech-stack components (python, react, kubernetes) match skills that my team has?
* Is there an active user community for sharing knowledge?

## Project Inception

In 2017 and again in 2018, I participated in evaluations by two different teams of CI/CD frameworks such as CircleCI, Travis, GitLab and Jenkins at my workplace. We considered 18 such tools in the first, and about 10 in the second. Interestingly, the outcome of the second eval was quite different: where Jenkins handily beat its rivals in 2017, emergence of Kubernetes and a colossal infusion of equity investment into GitLab put this product out front. Starting from a newer codebase, much of the new engineering effort at GitLab focused on container workflow and integration with Kubernetes.

In 2019, as a hobby effort I replaced an old party-invitations perl script (DaVite) with a python-based events-management tool and put it online as https://www.conclave.events. By early 2020, I was planning to promote this as an alternative to Meetup.Com for real-life gatherings. When COVID-19 disrupted those plans, the efforts of a Seattle teenager who launched one of the most widely-used tracker sites within the first couple weeks (http://ncov2019.live) inspired me to redirect energy into refactoring and documenting the Conclave code as a Kubernetes python/react.js framework. The intent now is to empower many more future teenagers with the same tools I've been using professionally.

## The Hard Problems

Each portion of the framework may be simple and straightforward to use, from the perspective of someone who is familiar with the technology. But getting them all working in concert is daunting even for people with broad "full-stack developer" career skills. And as the technologies evolve, it's becoming increasingly difficult to stay on top of the technologies for those who pursue the full-stack challenge. A CTO at my former employer described Kubernetes as the "operating system of the future", yet even Kubernetes mastery doesn't provide the full requirements for success.

* For back-end developers new to JavaScript, programming with React.js requires un-learning habits and figuring out whole new concepts
* For front-end developers, sluggish and flaky CI pipelines are difficult to work with; many would rather do away with devops teams entirely
* Setting up CI/CD pipelines has always been tedious and frustrating
* Kubernetes, already vast and complex, is going through rapid evolution and several breaking-changes releases each year
* Role-based access control is almost always left as an exercise for the developer by previous frameworks
* Single-signon is tedious to get working in any new application
* Test development and maintenance continues to drain half, sometimes even more, of the engineering hours required to build a high-quality online service
* Persistent-data storage for databases, pictures and videos for 12-factor applications has never been standardized and Kubernetes still has no cross-vendor answer to the problem
* Service-registration with tools like etcd and zookeeper has a steep learning curve, but it's an essential ingredient of most online services
* Message-passing and background processing is often implemented inconsistently even though there are standards like Amazon SQS and RabbitMQ (the one included in this framework)
* When applications are launched in a single language (usually English), internationalization is often costly to add later
* Monetizing an application to pay for its own hosting and engineering support requires billing and usage-tracking that remain difficult to implement
* SQLAlchemy and Alembic are labor-intensive to set up, and schema changes require manual effort

While this framework doesn't solve those problems itself, here they are brought together in one place. If this framework were to take off, crowd-sourced solutions could be brought to bear on such challenges.
