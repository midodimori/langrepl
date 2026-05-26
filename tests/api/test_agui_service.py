"""Tests for AG-UI agent service."""

from __future__ import annotations

import itertools
from pathlib import Path
from unittest.mock import MagicMock

from ag_ui.core import EventType, RawEvent, TextMessageContentEvent

from langrepl.agents.context import AgentContext
from langrepl.api.service.agui import LangreplAGUIAgent, build_agent_context
from langrepl.configs import ApprovalMode


class TestBuildAgentContext:
    """Tests for build_agent_context helper."""

    def test_builds_context_with_defaults(self, temp_dir: Path):
        ctx = build_agent_context(working_dir=temp_dir)

        assert ctx.working_dir == temp_dir
        assert ctx.approval_mode == ApprovalMode.SEMI_ACTIVE
        assert ctx.platform != ""
        assert ctx.current_date_time_zoned != ""

    def test_builds_context_with_custom_approval_mode(self, temp_dir: Path):
        ctx = build_agent_context(
            working_dir=temp_dir,
            approval_mode=ApprovalMode.AGGRESSIVE,
        )
        assert ctx.approval_mode == ApprovalMode.AGGRESSIVE


class TestLangreplAGUIAgentContextInjection:
    """Tests for AgentContext injection via get_stream_kwargs."""

    def test_injects_pregel_runtime(self, temp_dir: Path):
        mock_graph = MagicMock()
        agent = LangreplAGUIAgent(
            name="test",
            graph=mock_graph,
            working_dir=temp_dir,
        )

        kwargs = agent.get_stream_kwargs(
            input={"messages": []},
            config={"configurable": {"thread_id": "t1"}},
        )

        runtime = kwargs["config"]["configurable"]["__pregel_runtime"]
        assert runtime.context.working_dir == temp_dir
        assert runtime.context.approval_mode == ApprovalMode.SEMI_ACTIVE

    def test_preserves_existing_config(self, temp_dir: Path):
        mock_graph = MagicMock()
        agent = LangreplAGUIAgent(
            name="test",
            graph=mock_graph,
            working_dir=temp_dir,
        )

        kwargs = agent.get_stream_kwargs(
            input={"messages": []},
            config={"configurable": {"thread_id": "t1", "custom_key": "val"}},
        )

        assert kwargs["config"]["configurable"]["thread_id"] == "t1"
        assert kwargs["config"]["configurable"]["custom_key"] == "val"
        assert "__pregel_runtime" in kwargs["config"]["configurable"]

    def test_clone_preserves_langrepl_context(self, temp_dir: Path):
        mock_graph = MagicMock()
        agent = LangreplAGUIAgent(
            name="test",
            graph=mock_graph,
            working_dir=temp_dir,
            approval_mode=ApprovalMode.AGGRESSIVE,
            description="desc",
            config={"configurable": {"thread_id": "base"}},
        )

        clone = agent.clone()

        assert clone is not agent
        assert clone.name == "test"
        assert clone.graph is mock_graph
        assert clone.working_dir == temp_dir
        assert clone.approval_mode == ApprovalMode.AGGRESSIVE
        assert clone.description == "desc"
        assert clone.config == {"configurable": {"thread_id": "base"}}

    def test_schema_keys_inspects_context_without_instantiation(self, temp_dir: Path):
        mock_graph = MagicMock()
        mock_graph.get_input_jsonschema.return_value = {
            "properties": {"messages": {}, "foo": {}}
        }
        mock_graph.get_output_jsonschema.return_value = {"properties": {"bar": {}}}
        mock_graph.config_schema.return_value.schema.return_value = {
            "properties": {"configurable": {}}
        }
        mock_graph.context_schema = AgentContext

        agent = LangreplAGUIAgent(
            name="test",
            graph=mock_graph,
            working_dir=temp_dir,
        )

        keys = agent.get_schema_keys(config={})

        assert "foo" in keys["input"]
        assert "bar" in keys["output"]
        assert "configurable" in keys["config"]
        assert "approval_mode" in keys["context"]
        assert "working_dir" in keys["context"]


class TestLangreplAGUIAgentDispatchEvent:
    """Tests for MCP serialization safety in _dispatch_event."""

    def test_normal_event_passes_through(self, temp_dir: Path):
        mock_graph = MagicMock()
        agent = LangreplAGUIAgent(
            name="test",
            graph=mock_graph,
            working_dir=temp_dir,
        )

        event = TextMessageContentEvent(
            type=EventType.TEXT_MESSAGE_CONTENT,
            message_id="msg-1",
            delta="hello",
        )
        result = agent._dispatch_event(event)
        assert result.delta == "hello"

    def test_non_serializable_raw_event_fallback(self, temp_dir: Path):
        mock_graph = MagicMock()
        agent = LangreplAGUIAgent(
            name="test",
            graph=mock_graph,
            working_dir=temp_dir,
        )

        # Simulate an event with non-pickleable data (like itertools.count)
        non_serializable = {"counter": itertools.count()}
        event = RawEvent(
            type=EventType.RAW,
            event=non_serializable,
        )

        # Should not raise — fallback handles it
        result = agent._dispatch_event(event)
        assert result is not None
