import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from langrepl.mcp.client import MCPClient
from langrepl.tools.schema import ToolSchema


class TestMCPClientTools:
    @pytest.mark.asyncio
    async def test_tools_without_filters(self, create_mock_tool):
        mock_tool1 = create_mock_tool("tool1")
        mock_tool2 = create_mock_tool("tool2")

        client = MCPClient(
            connections={"server1": Mock()},
            enable_approval=False,
        )
        cast(Any, client).get_tools = AsyncMock(return_value=[mock_tool1, mock_tool2])

        tools = await client.tools()

        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_tools_with_include_filter(self, create_mock_tool):
        mock_tool1 = create_mock_tool("tool1")
        mock_tool2 = create_mock_tool("tool2")

        tool_filters = {"server1": {"include": ["tool1"], "exclude": []}}

        client = MCPClient(
            connections={"server1": Mock()},
            tool_filters=tool_filters,
            enable_approval=False,
        )
        cast(Any, client).get_tools = AsyncMock(return_value=[mock_tool1, mock_tool2])

        tools = await client.tools()

        assert len(tools) == 1
        assert tools[0].name == "tool1"

    @pytest.mark.asyncio
    async def test_tools_with_exclude_filter(self, create_mock_tool):
        mock_tool1 = create_mock_tool("tool1")
        mock_tool2 = create_mock_tool("tool2")

        tool_filters = {"server1": {"include": [], "exclude": ["tool2"]}}

        client = MCPClient(
            connections={"server1": Mock()},
            tool_filters=tool_filters,
            enable_approval=False,
        )
        cast(Any, client).get_tools = AsyncMock(return_value=[mock_tool1, mock_tool2])

        tools = await client.tools()

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
        cast(Any, client).get_tools = AsyncMock(return_value=[mock_tool])

        with pytest.raises(ValueError, match="Both include/exclude"):
            await client.tools()

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
        cast(Any, client).get_tools = AsyncMock(side_effect=get_tools_side_effect)

        tools = await client.tools()

        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_server_error_returns_empty(self):
        client = MCPClient(
            connections={"server1": Mock()},
            enable_approval=False,
        )
        cast(Any, client).get_tools = AsyncMock(side_effect=Exception("Server error"))

        tools = await client.tools()

        assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_tools_have_approval_metadata(self, create_mock_tool):
        mock_tool = create_mock_tool("tool1")

        client = MCPClient(
            connections={"server1": Mock()},
            enable_approval=True,
        )
        cast(Any, client).get_tools = AsyncMock(return_value=[mock_tool])

        tools = await client.tools()

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

        async def load_server(server_name: str):
            from langrepl.mcp.tool import MCPTool
            from langrepl.tools.schema import ToolSchema

            schema = ToolSchema.from_tool(mock_tool)
            proxy = MCPTool(server_name, schema, AsyncMock())
            proxy._loaded = mock_tool
            return [proxy]

        client._load_server = AsyncMock(side_effect=load_server)  # type: ignore[method-assign]
        client._cache.load = MagicMock(return_value=None)  # type: ignore[method-assign]

        tools = await client.tools()

        assert len(tools) == 1
        assert tools[0].name == "tool1"
        assert tools[0]._loaded == mock_tool  # type: ignore[attr-defined]
        client._load_server.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cache_used_when_available(self, create_mock_tool):
        mock_tool = create_mock_tool("tool1")

        client = MCPClient(
            connections={"server1": Mock()},
            enable_approval=False,
        )
        client._load_server = AsyncMock(return_value=[mock_tool])  # type: ignore[method-assign]
        client._cache.load = MagicMock(  # type: ignore[method-assign]
            return_value=[ToolSchema.from_tool(mock_tool)]
        )

        tools = await client.tools()

        assert tools
        client._load_server.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cache_invalidated_on_hash_mismatch(
        self, create_mock_tool, tmp_path: Path
    ):
        mock_tool = create_mock_tool("tool1")

        from langrepl.mcp.client import ServerMeta

        client = MCPClient(
            connections={"server1": Mock()},
            enable_approval=False,
            cache_dir=tmp_path,
            server_metadata={"server1": ServerMeta(hash="new_hash")},
        )

        async def load_server(server_name: str):
            from langrepl.mcp.tool import MCPTool
            from langrepl.tools.schema import ToolSchema

            schema = ToolSchema.from_tool(mock_tool)
            proxy = MCPTool(server_name, schema, AsyncMock())
            proxy._loaded = mock_tool
            return [proxy]

        client._load_server = AsyncMock(side_effect=load_server)  # type: ignore[method-assign]

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

        tools = await client.tools()

        assert len(tools) == 1
        assert tools[0].name == "tool1"
        client._load_server.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_server_failure_does_not_block_others(self, create_mock_tool):
        mock_tool = create_mock_tool("tool_ok")

        client = MCPClient(
            connections={"server1": Mock(), "server2": Mock()},
            enable_approval=False,
        )

        async def load_server(server_name: str):
            if server_name == "server1":
                raise RuntimeError("boom")
            from langrepl.mcp.tool import MCPTool
            from langrepl.tools.schema import ToolSchema

            schema = ToolSchema.from_tool(mock_tool)
            proxy = MCPTool(server_name, schema, AsyncMock())
            proxy._loaded = mock_tool
            return [proxy]

        client._cache.load = MagicMock(return_value=None)  # type: ignore[method-assign]
        client._load_server = AsyncMock(side_effect=load_server)  # type: ignore[method-assign]

        tools = await client.tools()

        assert len(tools) == 1
        assert tools[0].name == "tool_ok"

    @pytest.mark.asyncio
    async def test_invoke_timeout_set_in_metadata(self, create_mock_tool):
        from langrepl.mcp.client import ServerMeta

        mock_tool = create_mock_tool("tool1")

        client = MCPClient(
            connections={"server1": Mock()},
            enable_approval=False,
            server_metadata={"server1": ServerMeta(invoke_timeout=30.0)},
        )
        cast(Any, client).get_tools = AsyncMock(return_value=[mock_tool])

        tools = await client.tools()

        assert len(tools) == 1
        assert tools[0].metadata is not None
        assert tools[0].metadata.get("timeout") == 30.0
