"""MCP client - orchestrates caching, sessions, loading, and registry."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import Connection

from langrepl.core.logging import get_logger
from langrepl.mcp.cache import MCPCache
from langrepl.mcp.loader import MCPLoader
from langrepl.mcp.registry import MCPRegistry
from langrepl.mcp.session import MCPSessions
from langrepl.mcp.tool import MCPTool
from langrepl.tools.schema import ToolSchema

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

logger = get_logger(__name__)


@dataclass
class RepairConfig:
    """Repair configuration for a server."""

    command: list[str]
    timeout: int


@dataclass
class ServerMeta:
    """Per-server metadata for MCP client."""

    hash: str | None = None
    stateful: bool = False
    invoke_timeout: float | None = None
    repair: RepairConfig | None = None


class MCPClient(MultiServerMCPClient):
    """MCP client with caching, sessions, and tool management."""

    def __init__(
        self,
        connections: dict[str, Connection] | None = None,
        tool_filters: dict[str, dict] | None = None,
        enable_approval: bool = True,
        cache_dir: Path | None = None,
        server_metadata: dict[str, ServerMeta] | None = None,
    ) -> None:
        super().__init__(connections)
        self._server_metadata = server_metadata or {}
        self._enable_approval = enable_approval
        server_hashes = {k: v.hash for k, v in self._server_metadata.items() if v.hash}
        repairs = {k: v.repair for k, v in self._server_metadata.items() if v.repair}
        self._cache = MCPCache(cache_dir, server_hashes)
        self._registry = MCPRegistry(tool_filters)
        self._sessions = MCPSessions(self.session)
        self._loader = MCPLoader(
            lambda s: self.get_tools(server_name=s),
            self._sessions.get,
            self._sessions.close,
            repairs,
        )
        self._tools_cache: list[BaseTool] | None = None
        self._live: dict[str, dict[str, BaseTool]] = {}
        self._init_lock = asyncio.Lock()
        self._server_locks: dict[str, asyncio.Lock] = {}

    def _build_metadata(
        self, server: str, source: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Build tool metadata with timeout and approval config."""
        metadata: dict[str, Any] = dict(source) if source else {}
        meta = self._server_metadata.get(server)
        if meta and meta.invoke_timeout is not None:
            metadata["timeout"] = meta.invoke_timeout
        if self._enable_approval:
            metadata["approval_config"] = {"name_only": True, "always_approve": False}
        return metadata

    async def tools(self) -> list[BaseTool]:
        """Get all MCP tools (lazy-loaded proxies)."""
        if self._tools_cache is not None:
            return self._tools_cache

        async with self._init_lock:
            if self._tools_cache is not None:
                return self._tools_cache
            self._tools_cache = await self._load_all()
            return self._tools_cache

    async def _load_all(self) -> list[BaseTool]:
        tools: list[BaseTool] = []
        pending: list[str] = []
        cached_stateful: list[str] = []

        for server in self.connections:
            cached = await self._cache.load(server)
            if cached:
                tools.extend(self._wrap_cached(server, cached))
                # Track cached stateful servers for warmup
                meta = self._server_metadata.get(server)
                if meta and meta.stateful:
                    cached_stateful.append(server)
            else:
                pending.append(server)

        # Warm up sessions for cached stateful servers in parallel
        if cached_stateful:
            logger.debug(
                "Warming up sessions for %d stateful servers", len(cached_stateful)
            )
            warmup_results: list[Any] = await asyncio.gather(
                *(self._sessions.get(s) for s in cached_stateful),
                return_exceptions=True,
            )
            for warmup_server, warmup_result in zip(
                cached_stateful, warmup_results, strict=True
            ):
                if isinstance(warmup_result, BaseException):
                    logger.warning(
                        "Failed to warm up session for %s: %s. "
                        "Session will initialize on first tool invocation.",
                        warmup_server,
                        warmup_result,
                    )

        if pending:
            results = await asyncio.gather(
                *(self._load_server(s) for s in pending),
                return_exceptions=True,
            )
            for server, result in zip(pending, results, strict=True):
                if isinstance(result, ValueError):
                    raise result
                if isinstance(result, BaseException):
                    logger.error("Failed to load %s: %s", server, result)
                else:
                    tools.extend(result)

        return tools

    def _wrap_cached(self, server: str, schemas: list[ToolSchema]) -> list[BaseTool]:
        tools: list[BaseTool] = []
        for schema in schemas:
            if not self._registry.allowed(schema.name, server):
                continue
            if not self._registry.register(schema.name, server):
                continue
            metadata = self._build_metadata(server)
            tools.append(MCPTool(server, schema, self._load_live, metadata))
        return tools

    async def _load_server(self, server: str) -> list[BaseTool]:
        """Load tools from MCP server, register, cache, and populate _live."""
        meta = self._server_metadata.get(server)
        if meta and meta.stateful:
            raw = await self._loader.stateful(server)
        else:
            raw = await self._loader.stateless(server)

        filtered = [t for t in raw if self._registry.allowed(t.name, server)]
        for t in filtered:
            self._registry.register(t.name, server)

        self._live[server] = {t.name: t for t in filtered}

        if filtered:
            schemas = [ToolSchema.from_tool(t) for t in filtered]
            await self._cache.save(server, schemas)
            logger.info("MCP server '%s': loaded %d tools", server, len(filtered))

        return [self._wrap_loaded(server, t) for t in filtered]

    def _wrap_loaded(self, server: str, tool: BaseTool) -> MCPTool:
        schema = ToolSchema.from_tool(tool)
        metadata = self._build_metadata(server, tool.metadata)
        proxy = MCPTool(server, schema, self._load_live, metadata)
        proxy._loaded = tool
        return proxy

    async def _load_live(self, server: str, name: str) -> BaseTool | None:
        if server in self._live:
            return self._live[server].get(name)

        lock = self._server_locks.setdefault(server, asyncio.Lock())
        async with lock:
            if server in self._live:
                return self._live[server].get(name)
            await self._populate_live(server)
            return self._live.get(server, {}).get(name)

    async def _populate_live(self, server: str) -> None:
        """Fetch tools from MCP server and populate _live for invocation."""
        meta = self._server_metadata.get(server)
        if meta and meta.stateful:
            raw = await self._loader.stateful(server)
        else:
            raw = await self._loader.stateless(server)

        filtered = [t for t in raw if self._registry.allowed(t.name, server)]
        self._live[server] = {t.name: t for t in filtered}

    async def close(self) -> None:
        """Close all stateful sessions."""
        await self._sessions.close_all()

    @property
    def module_map(self) -> dict[str, str]:
        """Tool name to server name mapping."""
        return self._registry.module_map
