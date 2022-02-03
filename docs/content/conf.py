# Configuration file for the Sphinx documentation builder.

from sphinx_markdown_parser.parser import MarkdownParser

# -- Path setup --------------------------------------------------------------

import os
import sys

sys.path.insert(0, os.path.dirname(__file__) + '/../..')

from apicrud._version import __version__  # noqa

# -- Project information -----------------------------------------------------

project = 'APIcrud'
copyright = '2022, Rich Braun'
author = 'Rich Braun'
version = __version__
# The full version, including alpha/beta/rc tags
release = __version__

# -- General configuration ---------------------------------------------------

# coverage - finds undocumented python code
# mermaid - diagram tool
# napoleon - parse google-style docstrings
#            http://google.github.io/styleguide/pyguide.html
# todo - parse RST todo comments

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.coverage',
    'sphinx.ext.napoleon',
    'sphinx.ext.todo',
    'sphinx_markdown_tables',
    'sphinxcontrib.mermaid'
]

templates_path = ['_templates']
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

autodoc_default_options = dict(members=None)
autosummary_generate = True
autosummary_imported_members = False

# for MarkdownParser

def setup(app):
    app.add_source_suffix('.md', 'markdown')
    app.add_source_parser(MarkdownParser)
    app.add_config_value('markdown_parser_config', dict(
        auto_toc_tree_section='Content',
        enable_auto_doc_ref=True,
        enable_auto_toc_tree=True,
        enable_eval_rst=True,
        extensions=[
            'extra', 'nl2br', 'sane_lists', 'smarty', 'toc', 'wikilinks',
            'pymdownx.arithmatex',
        ],
    ), True)
