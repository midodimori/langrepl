"""Tests for SandboxMiddleware - permission blocking edge cases."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain_core.tools import ToolException

from src.agents.context import AgentContext
from src.configs import ApprovalMode, SandboxConfig, SandboxPermission, SandboxType
from src.mcp.tool import LazyMCPTool
from src.middleware.sandbox import SandboxMiddleware


class TestPermissionBlocking:
    """Tests for blocking tool execution when permissions are missing."""

    @pytest.fixture
    def middleware(self):
        return SandboxMiddleware()

    @pytest.fixture
    def mock_handler(self):
        return AsyncMock(
            return_value=ToolMessage(
                name="test_tool",
                content="handler result",
                tool_call_id="call_1",
            )
        )

    @pytest.fixture
    def mock_request_requiring_filesystem(self, create_mock_tool):
        tool = create_mock_tool("file_tool")
        tool.metadata = {
            "module_path": "src.tools.impl.file_system",
            "sandbox_permissions": [SandboxPermission.FILESYSTEM],
        }
        request = Mock(spec=ToolCallRequest)
        request.tool = tool
        request.tool_call = {"id": "call_1", "name": "file_tool", "args": {"p": "/"}}
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.SEMI_ACTIVE,
            working_dir=Path("/tmp"),
        )
        # Add serializable state and config for sandbox execution tests
        request.runtime.state = {"messages": [], "todos": [], "files": None}
        request.runtime.config = {"tags": [], "metadata": {}, "configurable": {}}
        request.runtime.tool_call_id = "call_1"
        return request

    @pytest.fixture
    def mock_request_requiring_network(self, create_mock_tool):
        tool = create_mock_tool("web_tool")
        tool.metadata = {
            "module_path": "src.tools.impl.web",
            "sandbox_permissions": [SandboxPermission.NETWORK],
        }
        request = Mock(spec=ToolCallRequest)
        request.tool = tool
        request.tool_call = {
            "id": "call_2",
            "name": "web_tool",
            "args": {"url": "http://example.com"},
        }
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.SEMI_ACTIVE,
            working_dir=Path("/tmp"),
        )
        # Add serializable state and config for sandbox execution tests
        request.runtime.state = {"messages": [], "todos": [], "files": None}
        request.runtime.config = {"tags": [], "metadata": {}, "configurable": {}}
        request.runtime.tool_call_id = "call_2"
        return request

    @pytest.mark.asyncio
    async def test_blocks_filesystem_tool_without_permission(
        self, middleware, mock_handler, mock_request_requiring_filesystem
    ):
        """Filesystem tool blocked when only NETWORK granted."""
        mock_executor = AsyncMock()
        mock_executor.config = SandboxConfig(
            name="network-only",
            type=SandboxType.SEATBELT,
            permissions=[SandboxPermission.NETWORK],
        )
        mock_request_requiring_filesystem.runtime.context.sandbox_executor = (
            mock_executor
        )

        with pytest.raises(ToolException) as exc_info:
            await middleware.awrap_tool_call(
                mock_request_requiring_filesystem, mock_handler
            )

        mock_handler.assert_not_called()
        assert "requires permissions not granted" in str(exc_info.value)
        assert "filesystem" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_blocks_network_tool_without_permission(
        self, middleware, mock_handler, mock_request_requiring_network
    ):
        """Network tool blocked when only FILESYSTEM granted."""
        mock_executor = AsyncMock()
        mock_executor.config = SandboxConfig(
            name="fs-only",
            type=SandboxType.SEATBELT,
            permissions=[SandboxPermission.FILESYSTEM],
        )
        mock_request_requiring_network.runtime.context.sandbox_executor = mock_executor

        with pytest.raises(ToolException) as exc_info:
            await middleware.awrap_tool_call(
                mock_request_requiring_network, mock_handler
            )

        mock_handler.assert_not_called()
        assert "requires permissions not granted" in str(exc_info.value)
        assert "network" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_blocks_when_no_permissions_granted(
        self, middleware, mock_handler, mock_request_requiring_filesystem
    ):
        """Tool blocked when sandbox has empty permissions."""
        mock_executor = AsyncMock()
        mock_executor.config = SandboxConfig(
            name="locked",
            type=SandboxType.SEATBELT,
            permissions=[],
        )
        mock_request_requiring_filesystem.runtime.context.sandbox_executor = (
            mock_executor
        )

        with pytest.raises(ToolException) as exc_info:
            await middleware.awrap_tool_call(
                mock_request_requiring_filesystem, mock_handler
            )

        mock_handler.assert_not_called()
        assert "requires permissions not granted" in str(exc_info.value)
        assert "filesystem" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_allows_when_permission_granted(
        self, middleware, mock_handler, mock_request_requiring_filesystem
    ):
        """Tool executes when required permission is granted."""
        mock_executor = AsyncMock()
        mock_executor.config = SandboxConfig(
            name="full",
            type=SandboxType.SEATBELT,
            permissions=[SandboxPermission.NETWORK, SandboxPermission.FILESYSTEM],
        )
        mock_executor.execute.return_value = {"success": True, "content": "ok"}
        mock_request_requiring_filesystem.runtime.context.sandbox_executor = (
            mock_executor
        )

        result = await middleware.awrap_tool_call(
            mock_request_requiring_filesystem, mock_handler
        )

        mock_executor.execute.assert_called_once()
        assert result.content == "ok"

    @pytest.mark.asyncio
    async def test_tool_without_permission_requirements_blocked(
        self, middleware, mock_handler, create_mock_tool
    ):
        """Tool without sandbox_permissions metadata is blocked (deny-by-default)."""
        tool = create_mock_tool("no_perm_tool")
        tool.metadata = {"module_path": "src.tools.impl.test"}
        request = Mock(spec=ToolCallRequest)
        request.tool = tool
        request.tool_call = {"id": "call_1", "name": "no_perm_tool", "args": {}}
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.SEMI_ACTIVE,
            working_dir=Path("/tmp"),
        )

        mock_executor = AsyncMock()
        mock_executor.config = SandboxConfig(
            name="restricted",
            type=SandboxType.SEATBELT,
            permissions=[],
        )
        request.runtime.context.sandbox_executor = mock_executor

        with pytest.raises(ToolException) as exc_info:
            await middleware.awrap_tool_call(request, mock_handler)

        mock_handler.assert_not_called()
        assert "no declared sandbox_permissions" in str(exc_info.value)


class TestMcpToolsBypass:
    """Tests for MCP tools bypassing sandbox middleware."""

    @pytest.fixture
    def middleware(self):
        return SandboxMiddleware()

    @pytest.fixture
    def mock_handler(self):
        return AsyncMock(
            return_value=ToolMessage(
                name="mcp_tool",
                content="mcp result",
                tool_call_id="call_1",
            )
        )

    @pytest.mark.asyncio
    async def test_mcp_tools_with_no_permissions_blocked(
        self, middleware, mock_handler
    ):
        """MCP tools with no permission requirements are blocked (deny-by-default)."""
        request = Mock(spec=ToolCallRequest)
        request.tool = Mock(spec=LazyMCPTool)
        request.tool.name = "mcp_tool"
        request.tool.metadata = {}  # No sandbox_permissions = blocked
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.SEMI_ACTIVE,
            working_dir=Path("/tmp"),
        )

        mock_executor = AsyncMock()
        mock_executor.config = SandboxConfig(
            name="locked",
            type=SandboxType.SEATBELT,
            permissions=[],
        )
        request.runtime.context.sandbox_executor = mock_executor

        with pytest.raises(ToolException) as exc_info:
            await middleware.awrap_tool_call(request, mock_handler)

        mock_handler.assert_not_called()
        assert "no declared sandbox_permissions" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_mcp_tools_blocked_without_required_permission(
        self, middleware, mock_handler
    ):
        """MCP tools blocked when required permissions not granted."""
        request = Mock(spec=ToolCallRequest)
        request.tool = Mock(spec=LazyMCPTool)
        request.tool.name = "mcp_tool"
        request.tool.metadata = {"sandbox_permissions": [SandboxPermission.NETWORK]}
        request.tool_call = {"id": "call_1", "name": "mcp_tool", "args": {}}
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.SEMI_ACTIVE,
            working_dir=Path("/tmp"),
        )

        # Sandbox only has FILESYSTEM, not NETWORK
        mock_executor = AsyncMock()
        mock_executor.config = SandboxConfig(
            name="fs-only",
            type=SandboxType.SEATBELT,
            permissions=[SandboxPermission.FILESYSTEM],
        )
        request.runtime.context.sandbox_executor = mock_executor

        with pytest.raises(ToolException) as exc_info:
            await middleware.awrap_tool_call(request, mock_handler)

        mock_handler.assert_not_called()
        assert "requires permissions not granted" in str(exc_info.value)
        assert "network" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_mcp_tools_pass_with_matching_permissions(
        self, middleware, mock_handler
    ):
        """MCP tools pass when sandbox grants required permissions."""
        request = Mock(spec=ToolCallRequest)
        request.tool = Mock(spec=LazyMCPTool)
        request.tool.name = "mcp_tool"
        request.tool.metadata = {"sandbox_permissions": [SandboxPermission.NETWORK]}
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.SEMI_ACTIVE,
            working_dir=Path("/tmp"),
        )

        mock_executor = AsyncMock()
        mock_executor.config = SandboxConfig(
            name="full",
            type=SandboxType.SEATBELT,
            permissions=[SandboxPermission.NETWORK, SandboxPermission.FILESYSTEM],
        )
        request.runtime.context.sandbox_executor = mock_executor

        result = await middleware.awrap_tool_call(request, mock_handler)

        mock_handler.assert_called_once()
        assert result.content == "mcp result"


class TestPassthroughConditions:
    """Tests for conditions that cause passthrough to handler."""

    @pytest.fixture
    def middleware(self):
        return SandboxMiddleware()

    @pytest.fixture
    def mock_handler(self):
        return AsyncMock(
            return_value=ToolMessage(
                name="test",
                content="handler result",
                tool_call_id="call_1",
            )
        )

    @pytest.mark.asyncio
    async def test_passthrough_when_no_sandbox_executor(
        self, middleware, mock_handler, create_mock_tool
    ):
        """No sandbox_executor means no sandboxing."""
        tool = create_mock_tool("test_tool")
        tool.metadata = {
            "module_path": "src.tools.impl.test",
            "sandbox_permissions": [SandboxPermission.FILESYSTEM],
        }
        request = Mock(spec=ToolCallRequest)
        request.tool = tool
        request.tool_call = {"id": "call_1", "name": "test_tool", "args": {}}
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.SEMI_ACTIVE,
            working_dir=Path("/tmp"),
        )
        request.runtime.context.sandbox_executor = None

        result = await middleware.awrap_tool_call(request, mock_handler)

        mock_handler.assert_called_once()
        assert result.content == "handler result"

    @pytest.mark.asyncio
    async def test_passthrough_when_sandbox_bypass(
        self, middleware, mock_handler, create_mock_tool
    ):
        """Tool with sandbox_bypass=True bypasses sandbox execution."""
        tool = create_mock_tool("test_tool")
        tool.metadata = {"sandbox_bypass": True}
        request = Mock(spec=ToolCallRequest)
        request.tool = tool
        request.tool_call = {"id": "call_1", "name": "test_tool", "args": {}}
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.SEMI_ACTIVE,
            working_dir=Path("/tmp"),
        )

        mock_executor = AsyncMock()
        mock_executor.config = SandboxConfig(
            name="test",
            type=SandboxType.SEATBELT,
            permissions=[],
        )
        request.runtime.context.sandbox_executor = mock_executor

        result = await middleware.awrap_tool_call(request, mock_handler)

        mock_handler.assert_called_once()
        mock_executor.execute.assert_not_called()
        assert result.content == "handler result"


class TestErrorHandling:
    """Tests for error handling in sandbox execution."""

    @pytest.fixture
    def middleware(self):
        return SandboxMiddleware()

    @pytest.fixture
    def mock_handler(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_sandbox_error_includes_traceback(
        self, middleware, mock_handler, create_mock_tool
    ):
        """Sandbox errors include traceback in message."""
        tool = create_mock_tool("test_tool")
        tool.metadata = {
            "module_path": "src.tools.impl.test",
            "sandbox_permissions": [SandboxPermission.FILESYSTEM],
        }
        request = Mock(spec=ToolCallRequest)
        request.tool = tool
        request.tool_call = {"id": "call_1", "name": "test_tool", "args": {}}
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.SEMI_ACTIVE,
            working_dir=Path("/tmp"),
        )
        # Add serializable state and config for sandbox execution
        request.runtime.state = {"messages": [], "todos": [], "files": None}
        request.runtime.config = {"tags": [], "metadata": {}, "configurable": {}}
        request.runtime.tool_call_id = "call_1"

        mock_executor = AsyncMock()
        mock_executor.config = SandboxConfig(
            name="test",
            type=SandboxType.SEATBELT,
            permissions=[SandboxPermission.FILESYSTEM],
        )
        mock_executor.execute.return_value = {
            "success": False,
            "error": "Permission denied",
            "traceback": "Traceback (most recent call last):\n  File...",
        }
        request.runtime.context.sandbox_executor = mock_executor

        result = await middleware.awrap_tool_call(request, mock_handler)

        assert "Permission denied" in result.content
        assert "Traceback" in result.short_content
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_sandbox_error_without_traceback(
        self, middleware, mock_handler, create_mock_tool
    ):
        """Sandbox errors without traceback still work."""
        tool = create_mock_tool("test_tool")
        tool.metadata = {
            "module_path": "src.tools.impl.test",
            "sandbox_permissions": [SandboxPermission.FILESYSTEM],
        }
        request = Mock(spec=ToolCallRequest)
        request.tool = tool
        request.tool_call = {"id": "call_1", "name": "test_tool", "args": {}}
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.SEMI_ACTIVE,
            working_dir=Path("/tmp"),
        )
        # Add serializable state and config for sandbox execution
        request.runtime.state = {"messages": [], "todos": [], "files": None}
        request.runtime.config = {"tags": [], "metadata": {}, "configurable": {}}
        request.runtime.tool_call_id = "call_1"

        mock_executor = AsyncMock()
        mock_executor.config = SandboxConfig(
            name="test",
            type=SandboxType.SEATBELT,
            permissions=[SandboxPermission.FILESYSTEM],
        )
        mock_executor.execute.return_value = {
            "success": False,
            "error": "Sandbox violation",
        }
        request.runtime.context.sandbox_executor = mock_executor

        result = await middleware.awrap_tool_call(request, mock_handler)

        assert "Sandbox violation" in result.content
        assert "Traceback" not in result.content
