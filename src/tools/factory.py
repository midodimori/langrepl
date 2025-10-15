from langchain_core.tools import BaseTool

from src.tools.impl.file_system import FILE_SYSTEM_TOOLS
from src.tools.impl.grep_search import GREP_SEARCH_TOOLS
from src.tools.impl.terminal import TERMINAL_TOOLS
from src.tools.impl.web import WEB_TOOLS
from src.tools.internal.memory import MEMORY_TOOLS
from src.tools.internal.todo import TODO_TOOLS


class ToolFactory:
    def __init__(self):
        self.impl_tools = []
        self.internal_tools = []
        self._impl_module_map: dict[str, str] = {}
        self._internal_module_map: dict[str, str] = {}

        for tool_group in [
            FILE_SYSTEM_TOOLS,
            WEB_TOOLS,
            GREP_SEARCH_TOOLS,
            TERMINAL_TOOLS,
        ]:
            for tool in tool_group:
                func = getattr(tool, "func", None) or getattr(tool, "coroutine", None)
                if func:
                    module_name = func.__module__.split(".")[-1]
                    self._impl_module_map[tool.name] = module_name
            self.impl_tools.extend(tool_group)

        for tool_group in [MEMORY_TOOLS, TODO_TOOLS]:
            for tool in tool_group:
                func = getattr(tool, "func", None) or getattr(tool, "coroutine", None)
                if func:
                    module_name = func.__module__.split(".")[-1]
                    self._internal_module_map[tool.name] = module_name
            self.internal_tools.extend(tool_group)

    def get_impl_tools(self) -> list[BaseTool]:
        return self.impl_tools

    def get_internal_tools(self) -> list[BaseTool]:
        return self.internal_tools

    def get_impl_module_map(self) -> dict[str, str]:
        return self._impl_module_map

    def get_internal_module_map(self) -> dict[str, str]:
        return self._internal_module_map
