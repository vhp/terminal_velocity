"""Shared fixtures for the test suite."""

import os

import pytest


@pytest.fixture
def notes_dir(tmp_path):
    """A notes directory with three notes; "apple pie" is the oldest."""
    (tmp_path / "apple pie.txt").write_text("dessert recipe\nwith apples")
    (tmp_path / "applesauce.txt").write_text("also apples")
    (tmp_path / "banana.txt").write_text("yellow fruit")
    os.utime(tmp_path / "apple pie.txt", (1000, 1000))
    return tmp_path
