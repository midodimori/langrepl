"""Tests for sandbox runtime serialization."""

from __future__ import annotations

import uuid
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from langrepl.agents.context import AgentContext
from langrepl.configs import ApprovalMode
from langrepl.sandboxes.serialization import deserialize_runtime, serialize_runtime


class MockTodo(BaseModel):
    """Mock todo item for testing."""

    id: str
    content: str


@pytest.fixture
def agent_context(temp_dir) -> AgentContext:
    """Create a basic agent context."""
    return AgentContext(
        approval_mode=ApprovalMode.AGGRESSIVE,
        working_dir=temp_dir,
    )


def _create_runtime(
    agent_context: AgentContext,
    run_id: uuid.UUID | None = None,
    todos: list[MockTodo] | None = None,
    callbacks: list | None = None,
) -> ToolRuntime:
    """Create a ToolRuntime for testing."""
    state: dict[str, Any] = {"messages": [AIMessage(content="test message")]}
    if todos:
        state["todos"] = todos

    config: RunnableConfig = {
        "tags": ["test-tag"],
        "metadata": {"key": "value"},
        "recursion_limit": 25,
        "configurable": {"thread_id": "test-thread"},
    }
    if run_id:
        config["run_id"] = run_id
    if callbacks:
        config["callbacks"] = callbacks

    return ToolRuntime(
        state=state,
        context=cast(None, agent_context),
        config=config,
        stream_writer=lambda _: None,
        tool_call_id="test-call-id",
        store=None,
    )


class TestSerializeRuntime:
    """Tests for serialize_runtime function."""

    def test_serialize_excludes_messages(self, agent_context):
        """Messages should be excluded from serialized state."""
        runtime = _create_runtime(agent_context)

        result = serialize_runtime(runtime)

        assert "messages" not in result["state"]

    def test_serialize_excludes_callbacks(self, agent_context):
        """Callbacks should be removed from serialized config."""
        mock_callback = MagicMock()
        runtime = _create_runtime(agent_context, callbacks=[mock_callback])

        result = serialize_runtime(runtime)

        assert "callbacks" not in result["config"]

    def test_serialize_run_id_to_string(self, agent_context):
        """UUID run_id should be converted to string."""
        run_id = uuid.uuid4()
        runtime = _create_runtime(agent_context, run_id=run_id)

        result = serialize_runtime(runtime)

        assert result["config"]["run_id"] == str(run_id)

    def test_serialize_todos(self, agent_context):
        """Todos should be serialized via model_dump."""
        todos = [
            MockTodo(id="1", content="First todo"),
            MockTodo(id="2", content="Second todo"),
        ]
        runtime = _create_runtime(agent_context, todos=todos)

        result = serialize_runtime(runtime)

        assert result["state"]["todos"] == [
            {"id": "1", "content": "First todo"},
            {"id": "2", "content": "Second todo"},
        ]

    def test_serialize_preserves_tool_call_id(self, agent_context):
        """Tool call ID should be preserved."""
        runtime = _create_runtime(agent_context)

        result = serialize_runtime(runtime)

        assert result["tool_call_id"] == "test-call-id"

    def test_serialize_context_as_json(self, agent_context):
        """Context should be serialized as JSON dict."""
        runtime = _create_runtime(agent_context)

        result = serialize_runtime(runtime)

        assert isinstance(result["context"], dict)
        assert result["context"]["approval_mode"] == "aggressive"


class TestDeserializeRuntime:
    """Tests for deserialize_runtime function."""

    def test_deserialize_reconstructs_config(self, agent_context):
        """Config fields should be restored correctly."""
        runtime = _create_runtime(agent_context, run_id=uuid.uuid4())
        serialized = serialize_runtime(runtime)

        result = deserialize_runtime(serialized)

        assert result.config.get("tags") == ["test-tag"]
        assert result.config.get("metadata") == {"key": "value"}
        assert result.config.get("recursion_limit") == 25
        assert result.config.get("configurable") == {"thread_id": "test-thread"}
        assert isinstance(result.config.get("run_id"), uuid.UUID)

    def test_deserialize_restores_context(self, agent_context):
        """AgentContext should be reconstructed."""
        runtime = _create_runtime(agent_context)
        serialized = serialize_runtime(runtime)

        result = deserialize_runtime(serialized)

        assert result.context is not None
        assert result.context.approval_mode == ApprovalMode.AGGRESSIVE

    def test_deserialize_adds_empty_messages(self, agent_context):
        """Deserialized state should have empty messages list."""
        runtime = _create_runtime(agent_context)
        serialized = serialize_runtime(runtime)

        result = deserialize_runtime(serialized)

        assert result.state["messages"] == []

    def test_roundtrip_preserves_data(self, agent_context):
        """Serialize then deserialize should preserve essential data."""
        run_id = uuid.uuid4()
        todos = [MockTodo(id="1", content="Test todo")]
        runtime = _create_runtime(agent_context, run_id=run_id, todos=todos)

        serialized = serialize_runtime(runtime)
        result = deserialize_runtime(serialized)

        assert result.tool_call_id == "test-call-id"
        assert result.config.get("run_id") == run_id
        assert result.state["todos"] == [{"id": "1", "content": "Test todo"}]
        assert result.context is not None
        assert result.context.working_dir == agent_context.working_dir
