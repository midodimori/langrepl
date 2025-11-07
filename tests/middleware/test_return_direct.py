"""Tests for ReturnDirectMiddleware."""

from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.agents.state import AgentState
from src.middleware.return_direct import ReturnDirectMiddleware


class TestReturnDirectMiddleware:
    """Tests for ReturnDirectMiddleware class."""

    @pytest.mark.asyncio
    async def test_jumps_to_end_with_return_direct_tool_message(self, agent_context):
        """Test that middleware jumps to end when ToolMessage has return_direct=True."""
        middleware = ReturnDirectMiddleware()

        tool_msg = ToolMessage(
            name="test_tool",
            content="result",
            tool_call_id="call_1",
            return_direct=True,
        )

        state: AgentState = {
            "messages": [
                HumanMessage(content="test", id="msg_1"),
                AIMessage(
                    content="",
                    tool_calls=[{"id": "call_1", "name": "test_tool", "args": {}}],
                    id="msg_2",
                ),
                tool_msg,
            ],
            "todos": None,
            "files": {},
            "current_input_tokens": None,
            "current_output_tokens": None,
            "total_cost": None,
        }

        runtime = Mock()
        runtime.context = agent_context

        result = await middleware.abefore_model(state, runtime)

        assert result is not None
        assert result["jump_to"] == "end"

    @pytest.mark.asyncio
    async def test_does_not_jump_without_return_direct(self, agent_context):
        """Test that middleware does not jump when ToolMessage has return_direct=False."""
        middleware = ReturnDirectMiddleware()

        state: AgentState = {
            "messages": [
                HumanMessage(content="test", id="msg_1"),
                AIMessage(
                    content="",
                    tool_calls=[{"id": "call_1", "name": "test_tool", "args": {}}],
                    id="msg_2",
                ),
                ToolMessage(
                    name="test_tool",
                    content="result",
                    tool_call_id="call_1",
                    id="msg_3",
                ),
            ],
            "todos": None,
            "files": {},
            "current_input_tokens": None,
            "current_output_tokens": None,
            "total_cost": None,
        }

        runtime = Mock()
        runtime.context = agent_context

        result = await middleware.abefore_model(state, runtime)

        assert result is None

    @pytest.mark.asyncio
    async def test_checks_only_recent_tool_messages(self, agent_context):
        """Test that middleware only checks recent tool messages."""
        middleware = ReturnDirectMiddleware()

        # Old tool message with return_direct, but followed by other messages
        old_tool_msg = ToolMessage(
            name="old_tool",
            content="old result",
            tool_call_id="call_old",
            id="msg_3",
            return_direct=True,
        )

        state: AgentState = {
            "messages": [
                HumanMessage(content="old test", id="msg_1"),
                AIMessage(
                    content="",
                    tool_calls=[{"id": "call_old", "name": "old_tool", "args": {}}],
                    id="msg_2",
                ),
                old_tool_msg,
                HumanMessage(
                    content="new test", id="msg_4"
                ),  # Non-tool message breaks the sequence
                AIMessage(
                    content="",
                    tool_calls=[{"id": "call_new", "name": "new_tool", "args": {}}],
                    id="msg_5",
                ),
                ToolMessage(
                    name="new_tool",
                    content="new result",
                    tool_call_id="call_new",
                    id="msg_6",
                ),
            ],
            "todos": None,
            "files": {},
            "current_input_tokens": None,
            "current_output_tokens": None,
            "total_cost": None,
        }

        runtime = Mock()
        runtime.context = agent_context

        result = await middleware.abefore_model(state, runtime)

        # Should not jump because the latest tool message doesn't have return_direct
        assert result is None

    @pytest.mark.asyncio
    async def test_handles_empty_messages(self, agent_context):
        """Test that middleware handles empty message list."""
        middleware = ReturnDirectMiddleware()

        state: AgentState = {
            "messages": [],
            "todos": None,
            "files": {},
            "current_input_tokens": None,
            "current_output_tokens": None,
            "total_cost": None,
        }

        runtime = Mock()
        runtime.context = agent_context

        result = await middleware.abefore_model(state, runtime)

        assert result is None

    @pytest.mark.asyncio
    async def test_handles_multiple_recent_tool_messages(self, agent_context):
        """Test handling of multiple consecutive tool messages."""
        middleware = ReturnDirectMiddleware()

        # First tool message without return_direct
        tool_msg1 = ToolMessage(
            name="tool1",
            content="result1",
            tool_call_id="call_1",
            id="msg_3",
        )

        # Second tool message with return_direct
        tool_msg2 = ToolMessage(
            name="tool2",
            content="result2",
            tool_call_id="call_2",
            id="msg_4",
            return_direct=True,
        )

        state: AgentState = {
            "messages": [
                HumanMessage(content="test", id="msg_1"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {"id": "call_1", "name": "tool1", "args": {}},
                        {"id": "call_2", "name": "tool2", "args": {}},
                    ],
                    id="msg_2",
                ),
                tool_msg1,
                tool_msg2,  # Most recent
            ],
            "todos": None,
            "files": {},
            "current_input_tokens": None,
            "current_output_tokens": None,
            "total_cost": None,
        }

        runtime = Mock()
        runtime.context = agent_context

        result = await middleware.abefore_model(state, runtime)

        # Should jump because the most recent tool message has return_direct
        assert result is not None
        assert result["jump_to"] == "end"
