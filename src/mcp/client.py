from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import Connection

from mcp.shared.exceptions import McpError
from src.core.logging import get_logger
from src.mcp.tool import LazyMCPTool
from src.tools.schema import ToolSchema
from src.utils.bash import execute_bash_command

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

logger = get_logger(__name__)


class MCPClient(MultiServerMCPClient):
    def __init__(
        self,
        connections: dict[str, Connection] | None = None,
        tool_filters: dict[str, dict] | None = None,
        repair_commands: dict[str, list[str]] | None = None,
        enable_approval: bool = True,
        cache_dir: Path | None = None,
        server_hashes: dict[str, str] | None = None,
    ) -> None:
        self._tool_filters = tool_filters or {}
        self._repair_commands = repair_commands or {}
        self._enable_approval = enable_approval
        self._cache_dir = cache_dir
        self._server_hashes = server_hashes or {}
        self._tools_cache: list[BaseTool] | None = None
        self._module_map: dict[str, str] = {}
        self._live_tools: dict[str, dict[str, BaseTool]] = {}
        self._init_lock = asyncio.Lock()
        self._server_locks: dict[str, asyncio.Lock] = {}
        super().__init__(connections)

    def _is_mcp_error(self, exc: Exception) -> bool:
        if isinstance(exc, McpError):
            return True
        if isinstance(exc, ExceptionGroup):
            return any(self._is_mcp_error(e) for e in exc.exceptions)
        return False

    def _is_tool_allowed(self, tool_name: str, server_name: str) -> bool:
        filters = self._tool_filters.get(server_name)
        if not filters:
            return True

        include, exclude = filters.get("include", []), filters.get("exclude", [])
        if include and exclude:
            raise ValueError(
                f"Cannot specify both include and exclude for server {server_name}"
            )

        if include:
            return tool_name in include
        if exclude:
            return tool_name not in exclude
        return True

    def _filter_tools(self, tools: list[BaseTool], server_name: str) -> list[BaseTool]:
        return [tool for tool in tools if self._is_tool_allowed(tool.name, server_name)]

    @staticmethod
    async def _run_repair_command(command: list[str]) -> None:
        await execute_bash_command(command, timeout=300)

    def _get_cache_path(self, server_name: str) -> Path | None:
        if not self._cache_dir:
            return None
        return self._cache_dir / f"{server_name}.json"

    def _load_cached_schemas(self, server_name: str) -> list[ToolSchema] | None:
        path = self._get_cache_path(server_name)
        if not path or not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            cache_hash = None
            tools_data = data

            if isinstance(data, dict):
                cache_hash = data.get("hash")
                tools_data = data.get("tools", [])

            expected_hash = self._server_hashes.get(server_name)
            if expected_hash and cache_hash != expected_hash:
                return None

            return [ToolSchema.model_validate(item) for item in tools_data]
        except Exception as exc:
            logger.warning(
                "Failed to load cached schemas for %s: %s",
                server_name,
                exc,
                exc_info=exc,
            )
            return None

    def _save_cached_schemas(
        self, server_name: str, tool_schemas: list[ToolSchema]
    ) -> None:
        path = self._get_cache_path(server_name)
        if not path:
            return

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "hash": self._server_hashes.get(server_name),
                "tools": [ts.model_dump() for ts in tool_schemas],
            }
            path.write_text(json.dumps(data, ensure_ascii=True, indent=2))
        except Exception as exc:
            logger.warning(
                "Failed to save cached schemas for %s: %s",
                server_name,
                exc,
                exc_info=exc,
            )

    async def _get_server_tools(self, server_name: str) -> list[BaseTool]:
        try:
            tools = await self.get_tools(server_name=server_name)
            return self._filter_tools(tools, server_name)
        except Exception as e:
            if self._is_mcp_error(e) and server_name in self._repair_commands:
                await self._run_repair_command(self._repair_commands[server_name])
                tools = await self.get_tools(server_name=server_name)
                return self._filter_tools(tools, server_name)
            else:
                logger.error(
                    f"Error getting tools from server {server_name}: {e}",
                    exc_info=True,
                )
                return []

    def _apply_metadata(self, tool: BaseTool) -> None:
        if not self._enable_approval:
            return
        tool.metadata = tool.metadata or {}
        tool.metadata["approval_config"] = {
            "name_only": True,
            "always_approve": False,
        }

    def _register_tool(self, tool_name: str, server_name: str) -> bool:
        existing = self._module_map.get(tool_name)
        if existing and existing != server_name:
            logger.warning(
                "Skipping MCP tool %s from %s; already provided by %s",
                tool_name,
                server_name,
                existing,
            )
            return False
        self._module_map.setdefault(tool_name, server_name)
        return True

    def _prepare_server_tools(
        self, server_name: str, tools: list[BaseTool]
    ) -> list[BaseTool]:
        prepared = []
        for tool in tools:
            self._apply_metadata(tool)
            if self._register_tool(tool.name, server_name):
                prepared.append(tool)

        self._live_tools[server_name] = {tool.name: tool for tool in prepared}
        return prepared

    async def _load_live_tool(
        self, server_name: str, tool_name: str
    ) -> BaseTool | None:
        if (
            server_name in self._live_tools
            and tool_name in self._live_tools[server_name]
        ):
            return self._live_tools[server_name][tool_name]

        lock = self._server_locks.setdefault(server_name, asyncio.Lock())

        async with lock:
            if server_name in self._live_tools:
                return self._live_tools[server_name].get(tool_name)

            tools = await self._get_server_tools(server_name)
            self._prepare_server_tools(server_name, tools)
            return self._live_tools[server_name].get(tool_name)

    async def _load_and_cache_server(self, server_name: str) -> list[BaseTool]:
        tools = await self._get_server_tools(server_name)
        prepared = self._prepare_server_tools(server_name, tools)

        if prepared:
            tool_schemas = [ToolSchema.from_tool(t) for t in prepared]
            self._save_cached_schemas(server_name, tool_schemas)
        return prepared

    async def get_mcp_tools(self) -> list[BaseTool]:
        if self._tools_cache is not None:
            return self._tools_cache

        async with self._init_lock:
            if self._tools_cache is not None:
                return self._tools_cache

            tools: list[BaseTool] = []
            pending_servers: list[str] = []

            for server_name in self.connections.keys():
                cached = self._load_cached_schemas(server_name)
                if not cached:
                    pending_servers.append(server_name)
                    continue

                for tool_schema in cached:
                    if not self._is_tool_allowed(tool_schema.name, server_name):
                        continue
                    if not self._register_tool(tool_schema.name, server_name):
                        continue
                    lazy_tool = LazyMCPTool(
                        server_name,
                        tool_schema,
                        self._load_live_tool,
                    )
                    self._apply_metadata(lazy_tool)
                    tools.append(lazy_tool)

            if pending_servers:
                results = await asyncio.gather(
                    *[self._load_and_cache_server(s) for s in pending_servers],
                    return_exceptions=True,
                )

                for server_name, server_result in zip(
                    pending_servers, results, strict=True
                ):
                    if isinstance(server_result, ValueError):
                        raise server_result
                    if isinstance(server_result, Exception):
                        logger.error(
                            "Failed to load MCP server %s: %s",
                            server_name,
                            server_result,
                            exc_info=server_result,
                        )
                        continue
                    if isinstance(server_result, list):
                        for tool in server_result:
                            tool_schema = ToolSchema.from_tool(tool)
                            lazy_tool = LazyMCPTool(
                                server_name,
                                tool_schema,
                                self._load_live_tool,
                            )
                            lazy_tool._loaded = tool
                            self._apply_metadata(lazy_tool)
                            tools.append(lazy_tool)

            self._tools_cache = tools
            return self._tools_cache

    def get_mcp_module_map(self) -> dict[str, str]:
        return self._module_map
