"""MCP tool loading with repair command support."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from langchain_mcp_adapters.tools import load_mcp_tools
from mcp.shared.exceptions import McpError

from langrepl.core.logging import get_logger
from langrepl.utils.bash import execute_bash_command

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool
    from mcp import ClientSession

    from langrepl.mcp.client import RepairConfig

logger = get_logger(__name__)


def _is_mcp_error(exc: Exception) -> bool:
    """Check if exception is MCP-related (supports ExceptionGroups)."""
    if isinstance(exc, McpError):
        return True
    if isinstance(exc, ExceptionGroup):
        return any(_is_mcp_error(e) for e in exc.exceptions)
    return False


class MCPLoader:
    """Loads tools from MCP servers with repair on failure."""

    def __init__(
        self,
        get_tools: Callable[[str], Awaitable[list[BaseTool]]],
        get_session: Callable[[str], Awaitable[ClientSession]],
        close_session: Callable[[str], Awaitable[None]],
        repairs: dict[str, RepairConfig] | None = None,
    ) -> None:
        self._get_tools = get_tools
        self._get_session = get_session
        self._close_session = close_session
        self._repairs = repairs or {}

    async def stateless(self, server: str) -> list[BaseTool]:
        """Load tools from stateless server."""
        return await self._with_repair(server, lambda: self._get_tools(server))

    async def stateful(self, server: str) -> list[BaseTool]:
        """Load tools from stateful server via persistent session."""

        async def load() -> list[BaseTool]:
            session = await self._get_session(server)
            return list(await load_mcp_tools(session))

        return await self._with_repair(server, load)

    async def _with_repair(
        self,
        server: str,
        load: Callable[[], Awaitable[list[BaseTool]]],
    ) -> list[BaseTool]:
        """Execute load with optional repair on MCP error."""
        try:
            return list(await load())
        except Exception as e:
            repair = self._repairs.get(server)
            if _is_mcp_error(e) and repair:
                await self._close_session(server)
                await execute_bash_command(repair.command, timeout=repair.timeout)
                return list(await load())
            logger.error("Failed to load tools from %s: %s", server, e, exc_info=True)
            return []
