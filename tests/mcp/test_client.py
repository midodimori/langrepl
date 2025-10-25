from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from src.mcp.client import MCPClient


def create_mock_tool(name: str) -> BaseTool:
    """Create a proper mock tool with required attributes."""

    class MockToolArgs(BaseModel):
        pass

    mock_tool = Mock(spec=BaseTool)
    mock_tool.name = name
    mock_tool.description = f"Mock tool {name}"
    mock_tool.args_schema = MockToolArgs
    mock_tool.handle_tool_error = False
    return mock_tool


class TestMCPClientGetTools:
    @pytest.mark.asyncio
    async def test_get_tools_without_filters(self):
        mock_tool1 = create_mock_tool("tool1")
        mock_tool2 = create_mock_tool("tool2")

        client = MCPClient(connections={"server1": Mock()}, enable_approval=False)
        client.get_tools = AsyncMock(return_value=[mock_tool1, mock_tool2])

        tools = await client.get_mcp_tools()

        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_get_tools_with_include_filter(self):
        mock_tool1 = create_mock_tool("tool1")
        mock_tool2 = create_mock_tool("tool2")

        tool_filters = {"server1": {"include": ["tool1"], "exclude": []}}

        client = MCPClient(
            connections={"server1": Mock()},
            tool_filters=tool_filters,
            enable_approval=False,
        )
        client.get_tools = AsyncMock(return_value=[mock_tool1, mock_tool2])

        tools = await client.get_mcp_tools()

        assert len(tools) == 1
        assert tools[0].name == "tool1"

    @pytest.mark.asyncio
    async def test_get_tools_with_exclude_filter(self):
        mock_tool1 = create_mock_tool("tool1")
        mock_tool2 = create_mock_tool("tool2")

        tool_filters = {"server1": {"include": [], "exclude": ["tool2"]}}

        client = MCPClient(
            connections={"server1": Mock()},
            tool_filters=tool_filters,
            enable_approval=False,
        )
        client.get_tools = AsyncMock(return_value=[mock_tool1, mock_tool2])

        tools = await client.get_mcp_tools()

        assert len(tools) == 1
        assert tools[0].name == "tool1"

    @pytest.mark.asyncio
    async def test_include_and_exclude_raises_error(self):
        mock_tool = create_mock_tool("tool1")

        tool_filters = {"server1": {"include": ["tool1"], "exclude": ["tool2"]}}

        client = MCPClient(
            connections={"server1": Mock()},
            tool_filters=tool_filters,
            enable_approval=False,
        )
        client.get_tools = AsyncMock(return_value=[mock_tool])

        tools = await client.get_mcp_tools()

        assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_multiple_servers(self):
        mock_tool1 = create_mock_tool("tool1")
        mock_tool2 = create_mock_tool("tool2")

        async def get_tools_side_effect(server_name):
            if server_name == "server1":
                return [mock_tool1]
            else:
                return [mock_tool2]

        client = MCPClient(
            connections={"server1": Mock(), "server2": Mock()}, enable_approval=False
        )
        client.get_tools = AsyncMock(side_effect=get_tools_side_effect)

        tools = await client.get_mcp_tools()

        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_server_error_returns_empty(self):
        client = MCPClient(connections={"server1": Mock()}, enable_approval=False)
        client.get_tools = AsyncMock(side_effect=Exception("Server error"))

        tools = await client.get_mcp_tools()

        assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_tools_wrapped_with_approval(self):
        mock_tool = create_mock_tool("tool1")

        client = MCPClient(connections={"server1": Mock()}, enable_approval=True)
        client.get_tools = AsyncMock(return_value=[mock_tool])

        tools = await client.get_mcp_tools()

        assert len(tools) == 1
        assert tools[0].__class__.__name__ == "ApprovedBaseTool"
