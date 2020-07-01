# Makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = content
BUILDDIR      = _build

VENV=python_env
VDIR=$(PWD)/$(VENV)

# Put it first so that "make" without argument is like "make help".
help: py_requirements
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

python_env: $(VDIR)/bin/python3

$(VDIR)/bin/python3:
	@echo "Creating virtual environment"
	python3 -m venv --system-site-packages $(VENV)

$(VDIR)/lib/python3.6/site-packages/sphinx/application.py: python_env
	@echo "Installing main requirements"
	. $(VDIR)/bin/activate && pip3 install -r requirements.txt
py_requirements: $(VDIR)/lib/python3.6/site-packages/sphinx/application.py

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
html: Makefile
	@. $(VDIR)/bin/activate && \
	$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O) && \
	$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" -b coverage $(O)
