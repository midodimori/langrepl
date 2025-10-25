import asyncio
from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import Connection

from src.core.logging import get_logger
from src.tools.wrapper import approval_tool

logger = get_logger(__name__)


class MCPToolWrapper(BaseTool):
    original_tool: BaseTool

    def __init__(self, tool: BaseTool, **kwargs: Any):
        super().__init__(
            name=tool.name,
            description=tool.description,
            args_schema=tool.args_schema,
            handle_tool_error=tool.handle_tool_error,
            original_tool=tool,
            **kwargs,
        )

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        kwargs = {k: v for k, v in kwargs.items() if k != "tool_call_id"}
        return self.original_tool._run(*args, **kwargs)

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        kwargs = {k: v for k, v in kwargs.items() if k != "tool_call_id"}
        return await self.original_tool._arun(*args, **kwargs)


class MCPClient(MultiServerMCPClient):
    def __init__(
        self,
        connections: dict[str, Connection] | None = None,
        tool_filters: dict[str, dict] | None = None,
        enable_approval: bool = True,
    ) -> None:
        self._tool_filters = tool_filters or {}
        self._enable_approval = enable_approval
        self._tools_cache: list[BaseTool] | None = None
        self._module_map: dict[str, str] = {}
        self._init_lock = asyncio.Lock()
        super().__init__(connections)

    async def _get_server_tools(self, server_name: str) -> list[BaseTool]:
        try:
            tools = await self.get_tools(server_name=server_name)
            if server_name not in self._tool_filters:
                return tools

            filters = self._tool_filters[server_name]
            include, exclude = filters.get("include", []), filters.get("exclude", [])

            if include and exclude:
                raise ValueError(
                    f"Cannot specify both include and exclude for server {server_name}"
                )

            if include:
                return [t for t in tools if t.name in include]
            if exclude:
                return [t for t in tools if t.name not in exclude]
            return tools
        except Exception as e:
            logger.error(f"Error getting tools from server {server_name}: {e}")
            return []

    async def get_mcp_tools(self) -> list[BaseTool]:
        if self._tools_cache:
            return self._tools_cache

        async with self._init_lock:
            if self._tools_cache:
                return self._tools_cache

            server_tools = await asyncio.gather(
                *[self._get_server_tools(s) for s in self.connections.keys()]
            )

            tools: list[BaseTool] = []
            for server_name, server_tool_list in zip(
                self.connections.keys(), server_tools
            ):
                for tool in server_tool_list:
                    wrapped_tool = MCPToolWrapper(tool)
                    self._module_map[wrapped_tool.name] = server_name
                    tools.append(wrapped_tool)

            if self._enable_approval:
                tools = [
                    approval_tool(name_only=True, always_approve=False)(t)
                    for t in tools
                ]

            self._tools_cache = tools
            return self._tools_cache

    def get_mcp_module_map(self) -> dict[str, str]:
        return self._module_map
