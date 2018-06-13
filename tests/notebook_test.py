import os
import pytest

from terminal_velocity.notebook import *


def test_notebook_constructor():
    """Create a notebook without raising an exception"""

    notebook_path = 'tests/data/tmp/'
    ext = '.md'
    exts = ['.md', '.txt']

    PlainTextNoteBook(notebook_path, extension=ext, extensions=exts)


def test_notebook_existing():
    """Notebook from existing folder"""

    notebook_path = 'tests/data/notebook_01/'
    ext = '.md'

    exts = ['.md', '.txt']
    assert len(
        PlainTextNoteBook(notebook_path, extension=ext, extensions=exts)) == 2

    exts.append('.csv')
    assert len(
        PlainTextNoteBook(notebook_path, extension=ext, extensions=exts)) == 3


def test_notebook_search():
    """Notebook's search functionality tests"""

    notebook_path = 'tests/data/notebook_01/'
    ext = '.md'
    exts = ['.md', '.txt']

    notebook = PlainTextNoteBook(notebook_path, extension=ext, extensions=exts)

    assert len([n for n in notebook.search("note")]) == 2
    assert len([n for n in notebook.search("note1")]) == 1
    assert len([n for n in notebook.search("topics")]) == 1
