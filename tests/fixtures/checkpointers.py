"""Checkpointer-related test fixtures."""

import uuid
from unittest.mock import AsyncMock

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import CheckpointTuple

from src.core.config import CheckpointerConfig, CheckpointerProvider


@pytest.fixture
def mock_checkpointer_tuple():
    """Create a mock CheckpointTuple for testing."""
    return CheckpointTuple(
        config=RunnableConfig(configurable={"thread_id": str(uuid.uuid4())}),
        checkpoint={
            "v": 1,
            "channel_values": {
                "messages": [],
                "current_input_tokens": 0,
                "current_output_tokens": 0,
                "total_cost": 0.0,
            },
            "channel_versions": {},
            "versions_seen": {},
            "updated_channels": [],
            "ts": "2024-01-01T00:00:00.000Z",
            "id": str(uuid.uuid4()),
        },
        metadata={},
        parent_config=None,
        pending_writes=None,
    )


@pytest.fixture
def mock_checkpointer(mock_checkpointer_tuple):
    """Create a mock LangGraph checkpointer with CheckpointTuple for integration tests."""
    checkpointer = AsyncMock()
    checkpointer.aget_tuple = AsyncMock(return_value=mock_checkpointer_tuple)
    checkpointer.alist = AsyncMock(return_value=[mock_checkpointer_tuple])
    checkpointer.aput = AsyncMock()

    return checkpointer


@pytest.fixture
def mock_checkpointer_config():
    """Create a mock CheckpointerConfig for testing."""
    return CheckpointerConfig(type=CheckpointerProvider.MEMORY)
