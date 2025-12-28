"""Tests for sandbox middleware."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from langrepl.agents.context import AgentContext
from langrepl.configs import ApprovalMode
from langrepl.middlewares.sandbox import SandboxMiddleware

if TYPE_CHECKING:
    pass


@dataclass
class MockToolCallRequest:
    """Mock ToolCallRequest for middleware tests."""

    tool_call: dict[str, Any]
    tool: BaseTool | None = None
    runtime: Any = None


def _create_runtime(working_dir: Path) -> ToolRuntime:
    """Create a ToolRuntime for testing."""
    context = AgentContext(
        approval_mode=ApprovalMode.AGGRESSIVE,
        working_dir=working_dir,
        tool_catalog=[],
    )
    return ToolRuntime(
        state={"messages": [AIMessage(content="test")]},
        context=cast(None, context),
        config=RunnableConfig(
            tags=["test"],
            metadata={},
            run_id=uuid.uuid4(),
        ),
        stream_writer=lambda _: None,
        tool_call_id="test-call-id",
        store=None,
    )


def _create_mock_tool(
    name: str, module: str = "langrepl.tools.impl.terminal"
) -> MagicMock:
    """Create a mock tool."""
    tool = MagicMock(spec=BaseTool)
    tool.name = name
    tool.metadata = {}
    tool.__module__ = module
    tool.func = MagicMock()
    tool.func.__module__ = module
    tool.func.__name__ = name
    return tool


class TestSandboxMiddleware:
    """Tests for SandboxMiddleware."""

    @pytest.mark.asyncio
    async def test_tool_not_in_map_returns_error(self, temp_dir: Path):
        """Tool not in tool_sandbox_map should return blocked message."""
        middleware = SandboxMiddleware(tool_sandbox_map={})
        request = MockToolCallRequest(
            tool_call={"id": "call-1", "name": "unknown_tool", "args": {}},
            tool=_create_mock_tool("unknown_tool"),
            runtime=_create_runtime(temp_dir),
        )
        handler = AsyncMock()

        result = await middleware.awrap_tool_call(request, handler)  # type: ignore[arg-type]

        assert isinstance(result, ToolMessage)
        assert "blocked" in result.content.lower()  # type: ignore[union-attr]
        assert "unknown_tool" in result.content  # type: ignore[operator]
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_backend_calls_handler_directly(self, temp_dir: Path):
        """backend=None means passthrough to handler."""
        middleware = SandboxMiddleware(tool_sandbox_map={"allowed_tool": None})
        request = MockToolCallRequest(
            tool_call={"id": "call-1", "name": "allowed_tool", "args": {}},
            tool=_create_mock_tool("allowed_tool"),
            runtime=_create_runtime(temp_dir),
        )
        expected_result = MagicMock()
        handler = AsyncMock(return_value=expected_result)

        result = await middleware.awrap_tool_call(request, handler)  # type: ignore[arg-type]

        handler.assert_called_once_with(request)
        assert result is expected_result

    @pytest.mark.asyncio
    async def test_catalog_proxy_extracts_underlying_tool(self, temp_dir: Path):
        """Catalog proxy should resolve underlying tool from tool_catalog."""
        # Create underlying tool in catalog
        underlying_tool = _create_mock_tool(
            "real_tool", "langrepl.tools.impl.filesystem"
        )

        # Create runtime with tool catalog
        context = AgentContext(
            approval_mode=ApprovalMode.AGGRESSIVE,
            working_dir=temp_dir,
            tool_catalog=[underlying_tool],
        )
        runtime: ToolRuntime = ToolRuntime(  # type: ignore[type-arg]
            state={"messages": []},
            context=cast(None, context),
            config=RunnableConfig(),
            stream_writer=lambda _: None,
            tool_call_id="call-1",
            store=None,
        )

        # Create proxy tool
        proxy_tool = MagicMock(spec=BaseTool)
        proxy_tool.name = "catalog_proxy"
        proxy_tool.metadata = {"approval_config": {"is_catalog_proxy": True}}

        # Backend should be looked up by underlying tool name
        mock_backend = MagicMock()
        mock_backend.execute = AsyncMock(
            return_value={"success": True, "content": "executed"}
        )

        middleware = SandboxMiddleware(tool_sandbox_map={"real_tool": mock_backend})
        request = MockToolCallRequest(
            tool_call={
                "id": "call-1",
                "name": "catalog_proxy",
                "args": {"tool_name": "real_tool", "tool_args": {"path": "/tmp"}},
            },
            tool=proxy_tool,
            runtime=runtime,
        )
        handler = AsyncMock()

        result = await middleware.awrap_tool_call(request, handler)  # type: ignore[arg-type]

        # Should have called backend.execute with underlying tool info
        mock_backend.execute.assert_called_once()
        call_args = mock_backend.execute.call_args
        assert call_args.kwargs["args"] == {"path": "/tmp"}

    @pytest.mark.asyncio
    async def test_sandbox_error_formats_message(self, temp_dir: Path):
        """Error result should include error + traceback + stderr."""
        mock_backend = MagicMock()
        mock_backend.execute = AsyncMock(
            return_value={
                "success": False,
                "error": "Permission denied",
                "traceback": "Traceback:\n  File...",
                "stderr": "Error output",
            }
        )

        middleware = SandboxMiddleware(tool_sandbox_map={"test_tool": mock_backend})
        request = MockToolCallRequest(
            tool_call={"id": "call-1", "name": "test_tool", "args": {}},
            tool=_create_mock_tool("test_tool"),
            runtime=_create_runtime(temp_dir),
        )
        handler = AsyncMock()

        result = await middleware.awrap_tool_call(request, handler)  # type: ignore[arg-type]

        assert isinstance(result, ToolMessage)
        assert "Permission denied" in str(result.content)
        assert "Traceback" in str(result.content)
        assert "Error output" in str(result.content)

    @pytest.mark.asyncio
    async def test_success_result_returns_tool_message(self, temp_dir: Path):
        """Successful result should create ToolMessage with content."""
        mock_backend = MagicMock()
        mock_backend.execute = AsyncMock(
            return_value={"success": True, "content": "File created successfully"}
        )

        middleware = SandboxMiddleware(tool_sandbox_map={"test_tool": mock_backend})
        request = MockToolCallRequest(
            tool_call={"id": "call-1", "name": "test_tool", "args": {}},
            tool=_create_mock_tool("test_tool"),
            runtime=_create_runtime(temp_dir),
        )
        handler = AsyncMock()

        result = await middleware.awrap_tool_call(request, handler)  # type: ignore[arg-type]

        assert isinstance(result, ToolMessage)
        assert result.content == "File created successfully"
        assert result.name == "test_tool"

    @pytest.mark.asyncio
    async def test_success_with_short_content(self, temp_dir: Path):
        """Result with short_content should be passed through."""
        mock_backend = MagicMock()
        mock_backend.execute = AsyncMock(
            return_value={
                "success": True,
                "content": "Long detailed output...",
                "short_content": "OK",
            }
        )

        middleware = SandboxMiddleware(tool_sandbox_map={"test_tool": mock_backend})
        request = MockToolCallRequest(
            tool_call={"id": "call-1", "name": "test_tool", "args": {}},
            tool=_create_mock_tool("test_tool"),
            runtime=_create_runtime(temp_dir),
        )
        handler = AsyncMock()

        result = await middleware.awrap_tool_call(request, handler)  # type: ignore[arg-type]

        assert isinstance(result, ToolMessage)
        assert result.content == "Long detailed output..."
        # short_content is passed to create_tool_message
        assert hasattr(result, "short_content") or "OK" in str(result)
