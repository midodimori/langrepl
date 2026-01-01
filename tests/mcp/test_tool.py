"""Tests for MCPTool."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.tools import ToolException

from langrepl.mcp.tool import MCPTool
from langrepl.tools.schema import ToolSchema


class TestMCPToolTimeout:
    @pytest.fixture
    def mock_schema(self):
        return ToolSchema(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
        )

    @pytest.fixture
    def slow_tool(self):
        async def slow_invoke(_):
            await asyncio.sleep(10)
            return "never"

        tool = Mock()
        tool.ainvoke = slow_invoke
        return tool

    @pytest.fixture
    def fast_tool(self):
        tool = Mock()
        tool.ainvoke = AsyncMock(return_value="success")
        return tool

    @pytest.mark.asyncio
    async def test_timeout_raises_tool_exception(self, mock_schema, slow_tool):
        loader = AsyncMock(return_value=slow_tool)
        mcp_tool = MCPTool("server1", mock_schema, loader)
        mcp_tool.metadata = {"timeout": 0.1}

        with pytest.raises(ToolException, match="timed out after 0.1s"):
            await mcp_tool._arun()

    @pytest.mark.asyncio
    async def test_no_timeout_when_not_set(self, mock_schema, fast_tool):
        loader = AsyncMock(return_value=fast_tool)
        mcp_tool = MCPTool("server1", mock_schema, loader)
        mcp_tool.metadata = {}

        result = await mcp_tool._arun()

        assert result == "success"

    @pytest.mark.asyncio
    async def test_completes_within_timeout(self, mock_schema, fast_tool):
        loader = AsyncMock(return_value=fast_tool)
        mcp_tool = MCPTool("server1", mock_schema, loader)
        mcp_tool.metadata = {"timeout": 10.0}

        result = await mcp_tool._arun()

        assert result == "success"
