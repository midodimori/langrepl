"""Shared fixtures for sandbox tests."""

from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from langrepl.agents.context import AgentContext
from langrepl.configs import ApprovalMode
from langrepl.configs.sandbox import (
    FilesystemConfig,
    NetworkConfig,
    SandboxConfig,
    SandboxOS,
    SandboxType,
)

# Platform detection
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform == "linux"


def get_current_sandbox_type() -> tuple[SandboxType, SandboxOS]:
    """Get sandbox type and OS for current platform."""
    if IS_MACOS:
        return SandboxType.SEATBELT, SandboxOS.MACOS
    return SandboxType.BUBBLEWRAP, SandboxOS.LINUX


@pytest.fixture
def sandbox_config() -> SandboxConfig:
    """Create a basic sandbox config for current platform."""
    sandbox_type, sandbox_os = get_current_sandbox_type()
    return SandboxConfig(
        name="test-sandbox",
        type=sandbox_type,
        os=sandbox_os,
        filesystem=FilesystemConfig(
            read=["."],
            write=["."],
            hidden=[],
        ),
        network=NetworkConfig(
            remote=["*"],
            local=[],
        ),
    )


@pytest.fixture
def sandbox_config_readonly() -> SandboxConfig:
    """Create a read-only sandbox config for current platform."""
    sandbox_type, sandbox_os = get_current_sandbox_type()
    return SandboxConfig(
        name="readonly-sandbox",
        type=sandbox_type,
        os=sandbox_os,
        filesystem=FilesystemConfig(
            read=["."],
            write=[],
            hidden=[],
        ),
        network=NetworkConfig(
            remote=[],
            local=[],
        ),
    )


@pytest.fixture
def sandbox_config_no_network() -> SandboxConfig:
    """Create a sandbox config with no network access."""
    sandbox_type, sandbox_os = get_current_sandbox_type()
    return SandboxConfig(
        name="no-network-sandbox",
        type=sandbox_type,
        os=sandbox_os,
        filesystem=FilesystemConfig(
            read=["."],
            write=["."],
            hidden=[],
        ),
        network=NetworkConfig(
            remote=[],
            local=[],
        ),
    )


@pytest.fixture
def agent_context(temp_dir: Path) -> AgentContext:
    """Create a basic agent context."""
    return AgentContext(
        approval_mode=ApprovalMode.AGGRESSIVE,
        working_dir=temp_dir,
    )


@pytest.fixture
def tool_runtime(agent_context: AgentContext) -> ToolRuntime:  # type: ignore[type-arg]
    """Create a ToolRuntime for testing."""
    from typing import cast

    return ToolRuntime(
        state={"messages": [AIMessage(content="test")]},
        context=cast(None, agent_context),
        config=RunnableConfig(
            tags=["test"],
            metadata={"key": "value"},
            run_id=uuid.uuid4(),
            callbacks=[],
        ),
        stream_writer=lambda _: None,
        tool_call_id="test-call-id",
        store=None,
    )


@pytest.fixture
def mock_sandbox_backend() -> MagicMock:
    """Create a mock sandbox backend."""
    backend = MagicMock()
    backend.execute = AsyncMock(
        return_value={"success": True, "content": "mock result"}
    )
    backend.name = "mock-sandbox"
    backend.type = SandboxType.SEATBELT
    return backend


@dataclass
class MockToolCallRequest:
    """Mock ToolCallRequest for middleware tests."""

    tool_call: dict[str, Any]
    tool: BaseTool | None = None
    runtime: ToolRuntime | None = None


@pytest.fixture
def mock_tool() -> MagicMock:
    """Create a mock tool."""
    tool = MagicMock(spec=BaseTool)
    tool.name = "test_tool"
    tool.metadata = {}
    tool.__module__ = "langrepl.tools.impl.terminal"
    tool.func = MagicMock()
    tool.func.__module__ = "langrepl.tools.impl.terminal"
    tool.func.__name__ = "run_command"
    return tool


@pytest.fixture
def mock_catalog_proxy_tool(mock_tool: MagicMock) -> MagicMock:
    """Create a mock catalog proxy tool."""
    proxy = MagicMock(spec=BaseTool)
    proxy.name = "catalog_tool"
    proxy.metadata = {"approval_config": {"is_catalog_proxy": True}}
    proxy.__module__ = "langrepl.tools.catalog"
    return proxy


def create_tool_call_request(
    tool_name: str,
    tool_args: dict[str, Any],
    tool: BaseTool | None = None,
    runtime: ToolRuntime | None = None,
    tool_call_id: str = "test-call-id",
) -> MockToolCallRequest:
    """Factory for creating mock ToolCallRequest objects."""
    return MockToolCallRequest(
        tool_call={
            "id": tool_call_id,
            "name": tool_name,
            "args": tool_args,
        },
        tool=tool,
        runtime=runtime,
    )
