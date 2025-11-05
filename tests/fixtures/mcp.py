"""MCP-related test fixtures."""

import pytest

from src.core.config import MCPConfig, MCPServerConfig


@pytest.fixture
def mock_mcp_server_config():
    """Create a mock MCP server config for testing."""
    return MCPServerConfig(
        command="python",
        args=["-m", "server"],
        transport="stdio",
        enabled=True,
    )


@pytest.fixture
def mock_mcp_config():
    """Create a mock MCP config with no servers for testing."""
    return MCPConfig(servers={})
