"""Tests for CompressToolOutputMiddleware."""

from unittest.mock import AsyncMock, Mock

import pytest
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from src.agents.context import AgentContext
from src.core.config import ApprovalMode
from src.middleware.compress_tool_output import CompressToolOutputMiddleware
from src.tools.internal.memory import read_memory_file


class TestCompressToolOutputMiddleware:
    """Tests for CompressToolOutputMiddleware class."""

    @pytest.mark.asyncio
    async def test_compresses_large_output(self, create_mock_tool, temp_dir):
        """Test that large tool output is compressed and stored in files."""
        model = FakeListChatModel(responses=["test"])
        middleware = CompressToolOutputMiddleware(model)

        # Create large content that exceeds token limit
        large_content = "x" * 10000  # Large string

        create_mock_tool("test_tool")
        request = Mock(spec=ToolCallRequest)
        request.tool_call = {"id": "call_1", "name": "test_tool"}
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.AGGRESSIVE,
            working_dir=temp_dir,
            tool_output_max_tokens=10,  # Low limit to trigger compression
        )

        # Mock handler that returns large output
        handler = AsyncMock(
            return_value=ToolMessage(
                name="test_tool",
                content=large_content,
                tool_call_id="call_1",
            )
        )

        result = await middleware.awrap_tool_call(request, handler)

        # Should return a Command with compressed message and file
        assert isinstance(result, Command)
        assert result.update is not None
        assert "messages" in result.update
        assert "files" in result.update

        # Check compressed message
        compressed_msg = result.update["messages"][0]
        assert "tool_output_call_1.txt" in compressed_msg.content
        assert "stored in virtual file" in compressed_msg.content

        # Check file was stored
        files = result.update["files"]
        assert "tool_output_call_1.txt" in files
        assert files["tool_output_call_1.txt"] == large_content

    @pytest.mark.asyncio
    async def test_does_not_compress_small_output(self, create_mock_tool, temp_dir):
        """Test that small output is not compressed."""
        model = FakeListChatModel(responses=["test"])
        middleware = CompressToolOutputMiddleware(model)

        small_content = "small output"

        create_mock_tool("test_tool")
        request = Mock(spec=ToolCallRequest)
        request.tool_call = {"id": "call_1", "name": "test_tool"}
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.AGGRESSIVE,
            working_dir=temp_dir,
            tool_output_max_tokens=10000,  # High limit, won't trigger
        )

        handler = AsyncMock(
            return_value=ToolMessage(
                name="test_tool",
                content=small_content,
                tool_call_id="call_1",
            )
        )

        result = await middleware.awrap_tool_call(request, handler)

        # Should return the original message
        assert isinstance(result, ToolMessage)
        assert result.content == small_content

    @pytest.mark.asyncio
    async def test_skips_compression_for_errors(self, create_mock_tool, temp_dir):
        """Test that error messages are not compressed."""
        model = FakeListChatModel(responses=["test"])
        middleware = CompressToolOutputMiddleware(model)

        error_content = "Error: " + ("x" * 10000)

        create_mock_tool("test_tool")
        request = Mock(spec=ToolCallRequest)
        request.tool_call = {"id": "call_1", "name": "test_tool"}
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.AGGRESSIVE,
            working_dir=temp_dir,
            tool_output_max_tokens=10,
        )

        # Create error message
        error_msg = ToolMessage(
            name="test_tool",
            content=error_content,
            tool_call_id="call_1",
        )
        error_msg.status = "error"  # Mark as error

        handler = AsyncMock(return_value=error_msg)

        result = await middleware.awrap_tool_call(request, handler)

        # Should not compress error messages
        assert isinstance(result, ToolMessage)
        assert result.content == error_content

    @pytest.mark.asyncio
    async def test_skips_compression_for_read_memory_file(self, temp_dir):
        """Test that read_memory_file output is not compressed."""
        model = FakeListChatModel(responses=["test"])
        middleware = CompressToolOutputMiddleware(model)

        large_content = "x" * 10000

        request = Mock(spec=ToolCallRequest)
        request.tool_call = {"id": "call_1", "name": read_memory_file.name}
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.AGGRESSIVE,
            working_dir=temp_dir,
            tool_output_max_tokens=10,
        )

        handler = AsyncMock(
            return_value=ToolMessage(
                name=read_memory_file.name,
                content=large_content,
                tool_call_id="call_1",
            )
        )

        result = await middleware.awrap_tool_call(request, handler)

        # Should not compress read_memory_file output
        assert isinstance(result, ToolMessage)
        assert result.content == large_content

    @pytest.mark.asyncio
    async def test_passes_through_command_from_handler(
        self, create_mock_tool, temp_dir
    ):
        """Test that Commands from handler are passed through."""
        model = FakeListChatModel(responses=["test"])
        middleware = CompressToolOutputMiddleware(model)

        create_mock_tool("test_tool")
        request = Mock(spec=ToolCallRequest)
        request.tool_call = {"id": "call_1", "name": "test_tool"}
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.AGGRESSIVE,
            working_dir=temp_dir,
        )

        # Handler returns a Command
        cmd: Command = Command(update={"messages": []})
        handler = AsyncMock(return_value=cmd)

        result = await middleware.awrap_tool_call(request, handler)

        # Should pass through the Command
        assert result is cmd

    @pytest.mark.asyncio
    async def test_handles_missing_max_tokens_config(self, create_mock_tool, temp_dir):
        """Test that middleware works when max_tokens is not configured."""
        model = FakeListChatModel(responses=["test"])
        middleware = CompressToolOutputMiddleware(model)

        large_content = "x" * 10000

        create_mock_tool("test_tool")
        request = Mock(spec=ToolCallRequest)
        request.tool_call = {"id": "call_1", "name": "test_tool"}
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.AGGRESSIVE,
            working_dir=temp_dir,
            # No tool_output_max_tokens set
        )

        handler = AsyncMock(
            return_value=ToolMessage(
                name="test_tool",
                content=large_content,
                tool_call_id="call_1",
            )
        )

        result = await middleware.awrap_tool_call(request, handler)

        # Should not compress when max_tokens is not set
        assert isinstance(result, ToolMessage)
        assert result.content == large_content

    @pytest.mark.asyncio
    async def test_handles_empty_content(self, create_mock_tool, temp_dir):
        """Test that middleware handles empty content."""
        model = FakeListChatModel(responses=["test"])
        middleware = CompressToolOutputMiddleware(model)

        create_mock_tool("test_tool")
        request = Mock(spec=ToolCallRequest)
        request.tool_call = {"id": "call_1", "name": "test_tool"}
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.AGGRESSIVE,
            working_dir=temp_dir,
            tool_output_max_tokens=10,
        )

        handler = AsyncMock(
            return_value=ToolMessage(
                name="test_tool",
                content="",
                tool_call_id="call_1",
            )
        )

        result = await middleware.awrap_tool_call(request, handler)

        # Should not compress empty content
        assert isinstance(result, ToolMessage)
        assert result.content == ""
