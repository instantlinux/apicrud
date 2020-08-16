## Docs
### About

This directory has files required to create open source documentation using [Sphinx](http://www.sphinx-doc.org/en/master/usage/installation.html). The project's source code is commented using docstrings specified in [Google Python Style Guide](https://github.com/google/styleguide/blob/gh-pages/pyguide.md).

### Configuration files
* **index.rst** - This is root of the “table of contents tree” (or toctree). This is one of the main things that Sphinx adds to reStructuredText, a way to connect multiple files to a single hierarchy of documents.
* **conf.py** - This is the build configuration file to customize Sphinx input and output behavior.
* **.rst files** - Used here to generate autodoc from docstrings of source directories.
* **.md files** - Documentation source itself.

```
./
├── docs
│   ├── content
│   │   ├── conf.py
│   │   ├── index.rst
│   │   ├── classes.rst
│   │   ├── example.rst
│   │   └── *.md
│   ├── Makefile
│   ├── requirements.txt
│   └── README.md
├── CONTRIBUTING.md
```

### Building the docs
1. Install sphinx and its dependencies
```
pip install -r pip-requirements.txt
```
2. Build the documents
```
make html
```
3. Access documents from **build/html/** folder.
