from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.tools import BaseTool

from src.core.logging import get_logger
from src.tools.schema import ToolSchema

logger = get_logger(__name__)


class LazyMCPTool(BaseTool):
    """Proxy MCP tool that hydrates on first invocation."""

    def __init__(
        self,
        server_name: str,
        tool_schema: ToolSchema,
        loader: Callable[[str, str], Awaitable[BaseTool | None]],
    ):
        super().__init__(
            name=tool_schema.name,
            description=tool_schema.description,
            args_schema=tool_schema.parameters,
        )
        self._server_name = server_name
        self._loader = loader
        self._loaded: BaseTool | None = None

    async def _ensure_tool(self) -> BaseTool:
        if not self._loaded:
            tool = await self._loader(self._server_name, self.name)
            if not tool:
                raise RuntimeError(
                    f"Failed to load MCP tool {self.name} from {self._server_name}"
                )
            self._loaded = tool
        return self._loaded

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        tool = await self._ensure_tool()
        if kwargs:
            return await tool.ainvoke(kwargs)
        if args:
            return await tool.ainvoke(args[0])
        return await tool.ainvoke({})

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        return asyncio.run(self._arun(*args, **kwargs))
