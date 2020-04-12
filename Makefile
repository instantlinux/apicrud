# Usage:
# See .gitlab-ci.yml for the main pipeline

MAXFAIL    ?= 1000
PYPI_URL   ?= https://upload.pypi.org/legacy/
PYPI_USER  ?= svc_docker
VERSION    ?= $(shell grep -o '[0-9.]*' apicrud/_version.py)
REGISTRY   ?= $(REGISTRY_URI)
export EXAMPLE_ENV ?= local

include example/Makefile.vars
include example/Makefile.dev
include example/Makefile.k8s

VENV=python_env
VDIR=$(PWD)/$(VENV)

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
	python3 -m virtualenv -p python3 --system-site-packages $(VENV)

flake8: test_requirements
	@echo "Running flake8 code analysis"
	. $(VDIR)/bin/activate && flake8 apicrud example tests \
	 --per-file-ignores='example/alembic/versions/*:E501,E122,E128' 

$(VDIR)/lib/python3.6/site-packages/pytest.py: python_env
	@echo "Installing test requirements"
	(. $(VDIR)/bin/activate && pip3 freeze && \
	 pip3 install -r tests/requirements.txt)
$(VDIR)/lib/python3.6/site-packages/flask/app.py: python_env
	@echo "Installing main requirements"
	(. $(VDIR)/bin/activate && \
	 pip3 install -r requirements.txt -r example/requirements.txt)
py_requirements: $(VDIR)/lib/python3.6/site-packages/flask/app.py
test_requirements: $(VDIR)/lib/python3.6/site-packages/pytest.py

test: test_requirements py_requirements
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
	 --cov .)

dist/apicrud-$(VERSION).tar.gz:
	@echo "Building package"
	pip show wheel >/dev/null; \
	if [ $$? -ne 0 ]; then \
	  (. $(VDIR)/bin/activate ; python setup.py sdist bdist_wheel); \
	else \
	  python setup.py sdist bdist_wheel ; \
	fi

clean:
	rm -rf build dist apicrud/htmlcov *.egg-info \
	 .cache .pytest_cache apicrud/__pycache__ tests/__pycache__
	find . -regextype egrep -regex \
         '.*(coverage.xml|results.xml|\.pyc|\.coverage|~)' -exec rm -rf {} \;
wipe_clean: clean
	rm -rf python_env
