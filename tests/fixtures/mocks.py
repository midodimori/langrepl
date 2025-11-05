"""Mock objects for graph and initializer."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio


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
    initializer.load_agent_config = AsyncMock(return_value=mock_agent_config)
    initializer.load_llm_config = AsyncMock(return_value=mock_llm_config)
    initializer.load_agents_config = AsyncMock(
        return_value=MagicMock(
            agents=[mock_agent_config],
            get_agent_config=MagicMock(return_value=mock_agent_config),
        )
    )
    initializer.load_llms_config = AsyncMock(
        return_value=MagicMock(
            llms=[mock_llm_config],
            get_llm_config=MagicMock(return_value=mock_llm_config),
        )
    )
    initializer.get_threads = AsyncMock(return_value=[])
    initializer.update_agent_llm = AsyncMock()
    initializer.update_default_agent = AsyncMock()
    initializer.load_user_memory = AsyncMock(return_value="")

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


@pytest_asyncio.fixture
async def config_dir(temp_dir, initializer):
    """Create and initialize config directory for tests."""
    await initializer._ensure_config_dir(temp_dir)
    return temp_dir
