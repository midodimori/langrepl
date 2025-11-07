import asyncio

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import Connection

from mcp.shared.exceptions import McpError
from src.core.logging import get_logger
from src.utils.bash import execute_bash_command

logger = get_logger(__name__)


class MCPClient(MultiServerMCPClient):
    def __init__(
        self,
        connections: dict[str, Connection] | None = None,
        tool_filters: dict[str, dict] | None = None,
        repair_commands: dict[str, list[str]] | None = None,
        enable_approval: bool = True,
    ) -> None:
        self._tool_filters = tool_filters or {}
        self._repair_commands = repair_commands or {}
        self._enable_approval = enable_approval
        self._tools_cache: list[BaseTool] | None = None
        self._module_map: dict[str, str] = {}
        self._init_lock = asyncio.Lock()
        super().__init__(connections)

    def _is_mcp_error(self, exc: Exception) -> bool:
        if isinstance(exc, McpError):
            return True
        if isinstance(exc, ExceptionGroup):
            return any(self._is_mcp_error(e) for e in exc.exceptions)
        return False

    def _filter_tools(self, tools: list[BaseTool], server_name: str) -> list[BaseTool]:
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

    @staticmethod
    async def _run_repair_command(command: list[str]) -> None:
        await execute_bash_command(command, timeout=300)

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
                    self._module_map[tool.name] = server_name

                    if self._enable_approval:
                        tool.metadata = tool.metadata or {}
                        tool.metadata["approval_config"] = {
                            "name_only": True,
                            "always_approve": False,
                        }

                    tools.append(tool)

            self._tools_cache = tools
            return self._tools_cache

    def get_mcp_module_map(self) -> dict[str, str]:
        return self._module_map
