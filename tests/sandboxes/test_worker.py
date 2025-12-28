"""Tests for sandbox worker logic."""

from __future__ import annotations

import pytest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from langrepl.sandboxes.worker import run, serialize_result


class TestSerializeResult:
    """Tests for serialize_result function."""

    def test_serialize_result_command(self):
        """Command should serialize with is_command=True."""
        command = Command(goto="next_node", update={"key": "value"})

        result = serialize_result(command)

        assert result["success"] is True
        assert result["is_command"] is True
        assert result["goto"] == "next_node"
        assert result["update"] == {"key": "value"}

    def test_serialize_result_tool_message(self):
        """ToolMessage should serialize with all fields."""
        message = ToolMessage(
            content="Tool executed successfully",
            name="test_tool",
            tool_call_id="call-123",
            status="success",
        )
        # Add optional attributes via setattr (these are dynamic)
        setattr(message, "short_content", "Success")
        setattr(message, "is_error", False)
        setattr(message, "return_direct", False)

        result = serialize_result(message)

        assert result["success"] is True
        assert result["content"] == "Tool executed successfully"
        assert result["name"] == "test_tool"
        assert result["status"] == "success"
        assert result["short_content"] == "Success"
        assert result["is_error"] is False
        assert result["return_direct"] is False

    def test_serialize_result_tool_message_missing_optional(self):
        """ToolMessage without optional attributes should have None values."""
        message = ToolMessage(
            content="Result",
            name="tool",
            tool_call_id="call-456",
        )

        result = serialize_result(message)

        assert result["success"] is True
        assert result["content"] == "Result"
        assert result.get("short_content") is None
        assert result.get("is_error") is None

    def test_serialize_result_plain_value(self):
        """Plain value should be wrapped with str()."""
        result = serialize_result({"data": [1, 2, 3]})

        assert result["success"] is True
        assert result["content"] == "{'data': [1, 2, 3]}"

    def test_serialize_result_string(self):
        """String value should be preserved."""
        result = serialize_result("Simple string result")

        assert result["success"] is True
        assert result["content"] == "Simple string result"


class TestRun:
    """Tests for run function."""

    @pytest.mark.asyncio
    async def test_run_rejects_invalid_module_prefix(self):
        """Modules outside langrepl.tools should be rejected."""
        result = await run(
            module_path="os.path",
            tool_name="join",
            args={},
        )

        assert result["success"] is False
        assert "not in allowed prefix" in result["error"]

    @pytest.mark.asyncio
    async def test_run_rejects_non_tool(self):
        """Objects without ainvoke should be rejected."""
        # Use a real module but non-tool function
        result = await run(
            module_path="langrepl.tools.impl.terminal",
            tool_name="__doc__",  # Not a tool
            args={},
        )

        assert result["success"] is False
        # Either "not a LangChain tool" or attribute error
        assert "error" in result

    @pytest.mark.asyncio
    async def test_run_handles_missing_tool(self):
        """Missing tool name should return error."""
        result = await run(
            module_path="langrepl.tools.impl.terminal",
            tool_name="nonexistent_tool_xyz",
            args={},
        )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_run_handles_import_error(self):
        """Non-existent module should return error."""
        result = await run(
            module_path="langrepl.tools.nonexistent_module",
            tool_name="some_tool",
            args={},
        )

        assert result["success"] is False
        assert "error" in result
