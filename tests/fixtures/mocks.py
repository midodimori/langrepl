"""Mock objects for graph and initializer."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_graph(mock_checkpointer):
    """Create a mock compiled graph for testing."""
    graph = AsyncMock()
    graph.checkpointer = mock_checkpointer
    graph.astream = AsyncMock()
    graph.aupdate_state = AsyncMock()
    graph.get_graph = MagicMock()
    return graph


@pytest.fixture
def mock_initializer(mock_agent_config, mock_llm_config, mock_checkpointer, mock_graph):
    """Create a mock initializer for testing."""
    initializer = MagicMock()
    initializer.get_threads = AsyncMock(return_value=[])
    initializer.load_user_memory = AsyncMock(return_value="")
    initializer.llm_factory = MagicMock()
    initializer.cached_tools_in_catalog = []
    initializer.cached_agent_skills = []
    initializer.cached_sandbox_executor = None

    @asynccontextmanager
    async def mock_get_checkpointer(*args, **kwargs):  # noqa: ARG001
        yield mock_checkpointer

    @asynccontextmanager
    async def mock_get_graph(*args, **kwargs):  # noqa: ARG001
        yield mock_graph

    initializer.get_checkpointer = mock_get_checkpointer
    initializer.get_graph = mock_get_graph

    return initializer


@pytest.fixture
def initializer():
    """Create a real Initializer instance for testing."""
    from src.cli.bootstrap.initializer import Initializer

    return Initializer()
