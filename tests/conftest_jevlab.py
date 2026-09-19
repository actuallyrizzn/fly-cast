"""Shared fixtures for the Jev lab. Loaded from tests/conftest.py."""

import pytest

from flycast.jevlab.data import load_split, smoke_root


@pytest.fixture
def smoke_task():
    """Load a committed smoke split: smoke_task('sst2', 'train') -> rows."""
    root = smoke_root()

    def load_named(task: str, split: str):
        return load_split(task, split, root=root)

    return load_named
