"""Root conftest.py - imports fixtures from modular structure."""

import tempfile
from pathlib import Path

import pytest

pytest_plugins = [
    "tests.fixtures.agents",
    "tests.fixtures.checkpointers",
    "tests.fixtures.cli",
    "tests.fixtures.images",
    "tests.fixtures.mcp",
    "tests.fixtures.mocks",
]


@pytest.fixture
def temp_dir():
    """Temporary directory for file operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
