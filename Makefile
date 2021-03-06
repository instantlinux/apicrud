# Usage:
# See .gitlab-ci.yml for the main pipeline
# See example/Makefile.dev for working locally
#
# To start all services in local kubernetes:
#   TAG=latest make deploy_local

MAXFAIL    ?= 1000
PYPI_URL   ?= https://upload.pypi.org/legacy/
PYPI_USER  ?= $(USER)
VERSION    ?= $(shell grep -o '[0-9.]*' apicrud/_version.py)
export APP_ENV  ?= local
export REGISTRY ?= $(REGISTRY_URI)/$(CI_PROJECT_PATH)

include example/Makefile.vars
include example/Makefile.dev
include example/Makefile.i18n
include example/Makefile.k8s
include example/Makefile.sops

VENV=python_env
VDIR=$(PWD)/$(VENV)
VER_PY=$(shell python3 -V |egrep -o '[1-9]+\.[0-9]+')

analysis: flake8
package: dist/apicrud-$(VERSION).tar.gz
publish: package
	@echo Publishing python package
	(. $(VDIR)/bin/activate && \
	 twine upload --repository-url $(PYPI_URL) \
	   -u $(PYPI_USER) -p $(PYPI_PASSWORD) dist/*)

test_functional:
	@echo "Run Functional Tests - not yet implemented"

python_env: $(VDIR)/bin/python3

$(VDIR)/bin/python3:
	@echo "Creating virtual environment"
	python3 -m venv --system-site-packages $(VENV)

example/openapi.yaml: $(wildcard example/openapi/*.yaml)
	@echo "Generating openapi.yaml"
	. $(VDIR)/bin/activate && dref example/openapi/api.yaml $@

# for the create_image rule, do this instead for openapi.yaml
openapi_deploy:
	pip install dollar-ref
	ls -l $(find . -name dref)
	/build/.local/bin/dref example/openapi/api.yaml example/openapi.yaml
	chmod 644 example/openapi.yaml

flake8: test_requirements
	@echo "Running flake8 code analysis"
	. $(VDIR)/bin/activate && flake8 apicrud example tests \
	 --per-file-ignores='example/alembic/versions/*:E501,E122,E128' 

$(VDIR)/lib/python$(VER_PY)/site-packages/pytest.py: python_env
	@echo "Installing test requirements"
	(. $(VDIR)/bin/activate && pip3 freeze && \
	 pip3 install -r tests/requirements.txt)
$(VDIR)/lib/python$(VER_PY)/site-packages/flask/app.py: python_env
	@echo "Installing main requirements"
	(. $(VDIR)/bin/activate && \
	 pip3 install -r requirements.txt)
py_requirements: $(VDIR)/lib/python$(VER_PY)/site-packages/flask/app.py
test_requirements: $(VDIR)/lib/python$(VER_PY)/site-packages/pytest.py

test: test_requirements py_requirements apicrud/i18n/en/LC_MESSAGES/messages.mo \
	  example/openapi.yaml
	@echo "Running pytest unit tests"
	cd apicrud && \
	(. $(VDIR)/bin/activate && \
	 PYTHONPATH=..:../example python3 -m pytest $(XARGS) ../tests \
	 --maxfail=$(MAXFAIL) \
	 --durations=10 \
	 --junitxml=../tests/results.xml \
	 --cov-report html \
	 --cov-report xml \
	 --cov-report term-missing \
	 --cov ../example \
	 --cov .)

dist/apicrud-$(VERSION).tar.gz: i18n_deploy test_requirements
	@echo "Building package"
	pip show wheel >/dev/null; \
	if [ $$? -ne 0 ]; then \
	  (. $(VDIR)/bin/activate ; python setup.py sdist bdist_wheel); \
	else \
	  python setup.py sdist bdist_wheel ; \
	fi

clean:
	rm -rf build dist *.egg-info .cache .pytest_cache */__pycache__ \
	 */*/__pycache__ */.coverage */.proto.sqlite */coverage.xml */htmlcov \
	 */results.xml docs/_build docs/content/stubs example/openapi.yaml
	find . -name '*.pyc' -or -name '*~' -or -name '*.created' \
	 -exec rm -rf {} \;
	find example -name __pycache__ -exec rm -rf {} \;
wipe_clean: clean
	find apicrud/i18n example/i18n -name '*.mo' -exec rm -rf {} \;
	rm -rf python_env
