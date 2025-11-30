import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from src.mcp.client import MCPClient
from src.tools.schema import ToolSchema


class TestMCPClientGetTools:
    @pytest.mark.asyncio
    async def test_get_tools_without_filters(self, create_mock_tool):
        mock_tool1 = create_mock_tool("tool1")
        mock_tool2 = create_mock_tool("tool2")

        client = MCPClient(
            connections={"server1": Mock()},
            enable_approval=False,
        )
        client.get_tools = AsyncMock(return_value=[mock_tool1, mock_tool2])

        tools = await client.get_mcp_tools()

        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_get_tools_with_include_filter(self, create_mock_tool):
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
    async def test_get_tools_with_exclude_filter(self, create_mock_tool):
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
    async def test_include_and_exclude_raises_error(self, create_mock_tool):
        mock_tool = create_mock_tool("tool1")

        tool_filters = {"server1": {"include": ["tool1"], "exclude": ["tool2"]}}

        client = MCPClient(
            connections={"server1": Mock()},
            tool_filters=tool_filters,
            enable_approval=False,
        )
        client.get_tools = AsyncMock(return_value=[mock_tool])

        tools = await client.get_mcp_tools()

        assert tools == []

    @pytest.mark.asyncio
    async def test_multiple_servers(self, create_mock_tool):
        mock_tool1 = create_mock_tool("tool1")
        mock_tool2 = create_mock_tool("tool2")

        async def get_tools_side_effect(server_name):
            if server_name == "server1":
                return [mock_tool1]
            else:
                return [mock_tool2]

        client = MCPClient(
            connections={"server1": Mock(), "server2": Mock()},
            enable_approval=False,
        )
        client.get_tools = AsyncMock(side_effect=get_tools_side_effect)

        tools = await client.get_mcp_tools()

        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_server_error_returns_empty(self):
        client = MCPClient(
            connections={"server1": Mock()},
            enable_approval=False,
        )
        client.get_tools = AsyncMock(side_effect=Exception("Server error"))

        tools = await client.get_mcp_tools()

        assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_tools_have_approval_metadata(self, create_mock_tool):
        mock_tool = create_mock_tool("tool1")

        client = MCPClient(
            connections={"server1": Mock()},
            enable_approval=True,
        )
        client.get_tools = AsyncMock(return_value=[mock_tool])

        tools = await client.get_mcp_tools()

        assert len(tools) == 1
        assert tools[0].metadata is not None
        assert "approval_config" in tools[0].metadata
        assert tools[0].metadata["approval_config"]["name_only"] is True
        assert tools[0].metadata["approval_config"]["always_approve"] is False

    @pytest.mark.asyncio
    async def test_cache_bypassed_when_missing(self, create_mock_tool):
        mock_tool = create_mock_tool("tool1")

        client = MCPClient(
            connections={"server1": Mock()},
            enable_approval=False,
        )

        async def load_and_cache_server(server_name: str):
            return [mock_tool]

        client._load_and_cache_server = AsyncMock(side_effect=load_and_cache_server)  # type: ignore[method-assign]
        client._load_cached_schemas = MagicMock(return_value=None)  # type: ignore[method-assign]

        tools = await client.get_mcp_tools()

        assert len(tools) == 1
        assert tools[0].name == "tool1"
        assert tools[0]._loaded == mock_tool  # type: ignore[attr-defined]
        client._load_and_cache_server.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cache_used_when_available(self, create_mock_tool):
        mock_tool = create_mock_tool("tool1")

        client = MCPClient(
            connections={"server1": Mock()},
            enable_approval=False,
        )
        client._load_and_cache_server = AsyncMock(return_value=[mock_tool])  # type: ignore[method-assign]
        client._load_cached_schemas = MagicMock(  # type: ignore[method-assign]
            return_value=[ToolSchema.from_tool(mock_tool)]
        )

        tools = await client.get_mcp_tools()

        assert tools
        client._load_and_cache_server.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cache_invalidated_on_hash_mismatch(
        self, create_mock_tool, tmp_path: Path
    ):
        mock_tool = create_mock_tool("tool1")

        client = MCPClient(
            connections={"server1": Mock()},
            enable_approval=False,
            server_hashes={"server1": "new_hash"},
            cache_dir=tmp_path,
        )

        async def load_and_cache_server(server_name: str):
            return [mock_tool]

        client._load_and_cache_server = AsyncMock(side_effect=load_and_cache_server)  # type: ignore[method-assign]

        cache_path = tmp_path / "server1.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cached_schema = ToolSchema.from_tool(mock_tool)
        cache_path.write_text(
            json.dumps(
                {"hash": "old_hash", "tools": [cached_schema.model_dump()]},
                ensure_ascii=True,
                indent=2,
            )
        )

        tools = await client.get_mcp_tools()

        assert len(tools) == 1
        assert tools[0].name == "tool1"
        client._load_and_cache_server.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_server_failure_does_not_block_others(self, create_mock_tool):
        mock_tool = create_mock_tool("tool_ok")

        client = MCPClient(
            connections={"server1": Mock(), "server2": Mock()},
            enable_approval=False,
        )
        client._load_cached_schemas = MagicMock(return_value=None)  # type: ignore[method-assign]
        client._load_and_cache_server = AsyncMock(  # type: ignore[method-assign]
            side_effect=[RuntimeError("boom"), [mock_tool]]
        )

        tools = await client.get_mcp_tools()

        assert len(tools) == 1
        assert tools[0].name == "tool_ok"
        assert client._load_and_cache_server.await_args_list[0].args[0] in (
            "server1",
            "server2",
        )
