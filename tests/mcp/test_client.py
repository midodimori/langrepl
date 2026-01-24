import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

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
        assert tools[0].name == "server1__tool1"

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
        assert tools[0].name == "server1__tool1"

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
    async def test_duplicate_tool_names_across_servers(self, create_mock_tool):
        """Both servers can have tools with the same name (prefixed with server name)."""
        mock_tool_s1 = create_mock_tool("search")
        mock_tool_s2 = create_mock_tool("search")

        async def get_tools_side_effect(server_name):
            if server_name == "server1":
                return [mock_tool_s1]
            else:
                return [mock_tool_s2]

        client = MCPClient(
            connections={"server1": Mock(), "server2": Mock()},
            enable_approval=False,
        )
        cast(Any, client).get_tools = AsyncMock(side_effect=get_tools_side_effect)

        tools = await client.tools()

        # Both tools should be registered with prefixed names
        assert len(tools) == 2
        tool_names = {t.name for t in tools}
        assert tool_names == {"server1__search", "server2__search"}

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
        client._cache.load = AsyncMock(return_value=None)  # type: ignore[method-assign]

        tools = await client.tools()

        assert len(tools) == 1
        assert tools[0].name == "server1__tool1"
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
        client._cache.load = AsyncMock(  # type: ignore[method-assign]
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
        assert tools[0].name == "server1__tool1"
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

        client._cache.load = AsyncMock(return_value=None)  # type: ignore[method-assign]
        client._load_server = AsyncMock(side_effect=load_server)  # type: ignore[method-assign]

        tools = await client.tools()

        assert len(tools) == 1
        assert tools[0].name == "server2__tool_ok"

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

    @pytest.mark.asyncio
    async def test_cached_stateful_server_warms_up_session(self, create_mock_tool):
        """Cached stateful servers should warm up sessions during tools()."""
        from langrepl.mcp.client import ServerMeta

        mock_tool = create_mock_tool("tool1")

        client = MCPClient(
            connections={"server1": Mock()},
            enable_approval=False,
            server_metadata={"server1": ServerMeta(stateful=True)},
        )
        client._cache.load = AsyncMock(  # type: ignore[method-assign]
            return_value=[ToolSchema.from_tool(mock_tool)]
        )
        client._sessions.get = AsyncMock(return_value=Mock())  # type: ignore[method-assign]

        await client.tools()

        client._sessions.get.assert_awaited_once_with("server1")

    @pytest.mark.asyncio
    async def test_cached_non_stateful_server_skips_warmup(self, create_mock_tool):
        """Non-stateful cached servers should NOT warm up sessions."""
        from langrepl.mcp.client import ServerMeta

        mock_tool = create_mock_tool("tool1")

        client = MCPClient(
            connections={"server1": Mock()},
            enable_approval=False,
            server_metadata={"server1": ServerMeta(stateful=False)},
        )
        client._cache.load = AsyncMock(  # type: ignore[method-assign]
            return_value=[ToolSchema.from_tool(mock_tool)]
        )
        client._sessions.get = AsyncMock()  # type: ignore[method-assign]

        await client.tools()

        client._sessions.get.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_warmup_failure_does_not_block_tools(self, create_mock_tool):
        """Failed warmup should log warning but still return tools."""
        from langrepl.mcp.client import ServerMeta

        mock_tool = create_mock_tool("tool1")

        client = MCPClient(
            connections={"server1": Mock()},
            enable_approval=False,
            server_metadata={"server1": ServerMeta(stateful=True)},
        )
        client._cache.load = AsyncMock(  # type: ignore[method-assign]
            return_value=[ToolSchema.from_tool(mock_tool)]
        )
        client._sessions.get = AsyncMock(  # type: ignore[method-assign]
            side_effect=RuntimeError("Connection failed")
        )

        tools = await client.tools()

        assert len(tools) == 1
        assert tools[0].name == "server1__tool1"

    @pytest.mark.asyncio
    async def test_multiple_stateful_servers_warmed_in_parallel(self, create_mock_tool):
        """Multiple stateful servers should be warmed up concurrently."""
        import asyncio
        import time

        from langrepl.mcp.client import ServerMeta

        mock_tool = create_mock_tool("tool1")

        client = MCPClient(
            connections={"server1": Mock(), "server2": Mock()},
            enable_approval=False,
            server_metadata={
                "server1": ServerMeta(stateful=True),
                "server2": ServerMeta(stateful=True),
            },
        )
        client._cache.load = AsyncMock(  # type: ignore[method-assign]
            return_value=[ToolSchema.from_tool(mock_tool)]
        )

        warmup_times: list[tuple[str, float]] = []

        async def track_warmup(server: str) -> Mock:
            warmup_times.append((server, time.time()))
            await asyncio.sleep(0.01)
            return Mock()

        client._sessions.get = AsyncMock(side_effect=track_warmup)  # type: ignore[method-assign]

        await client.tools()

        # Verify both servers warmed up
        assert len(warmup_times) == 2

        # Verify parallel execution: both should start within a small window
        # (not sequentially with 0.01s between starts)
        _, time1 = warmup_times[0]
        _, time2 = warmup_times[1]
        time_diff = abs(time2 - time1)
        assert time_diff < 0.005  # Started nearly simultaneously (parallel)

    @pytest.mark.asyncio
    async def test_non_cached_servers_skip_warmup(self, create_mock_tool):
        """Servers without cache should not trigger warmup (init in _load_server)."""
        from langrepl.mcp.client import ServerMeta

        mock_tool = create_mock_tool("tool1")

        client = MCPClient(
            connections={"server1": Mock()},
            enable_approval=False,
            server_metadata={"server1": ServerMeta(stateful=True)},
        )
        client._cache.load = AsyncMock(return_value=None)  # type: ignore[method-assign]

        async def mock_load_server(server_name: str):
            from langrepl.mcp.tool import MCPTool

            schema = ToolSchema.from_tool(mock_tool)
            proxy = MCPTool(server_name, schema, AsyncMock())
            proxy._loaded = mock_tool
            return [proxy]

        client._load_server = AsyncMock(side_effect=mock_load_server)  # type: ignore[method-assign]
        client._sessions.get = AsyncMock()  # type: ignore[method-assign]

        await client.tools()

        # Warmup should NOT be called (server loaded via _load_server instead)
        client._sessions.get.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_module_map_returns_prefixed_names(self, create_mock_tool):
        """module_map should map prefixed tool names to server names."""
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

        await client.tools()

        module_map = client.module_map
        assert module_map == {
            "server1__tool1": "server1",
            "server2__tool2": "server2",
        }
