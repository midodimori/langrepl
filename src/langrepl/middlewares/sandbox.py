"""Middleware for sandboxed tool execution."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langgraph.types import Command

from langrepl.agents import AgentState
from langrepl.agents.context import AgentContext
from langrepl.core.logging import get_logger
from langrepl.sandboxes.serialization import serialize_runtime
from langrepl.utils.render import create_tool_message

if TYPE_CHECKING:
    from langchain.tools.tool_node import ToolCallRequest

    from langrepl.sandboxes import SandboxBackend

logger = get_logger(__name__)


class SandboxMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Middleware to run tools in sandboxed subprocess."""

    def __init__(self, tool_sandbox_map: dict[str, SandboxBackend | None]):
        super().__init__()
        self.tool_sandbox_map = tool_sandbox_map

    def _get_sandbox_info(
        self, request: ToolCallRequest
    ) -> tuple[SandboxBackend | None, BaseTool | None, bool]:
        """Get sandbox backend and actual tool to execute.

        Returns:
            tuple: (backend, actual_tool, is_blocked)
        """
        tool_name = request.tool_call["name"]
        actual_tool: BaseTool | None = None

        # Check for catalog proxy - need to get underlying tool
        if request.tool:
            tool_metadata = request.tool.metadata or {}
            if (tool_metadata.get("approval_config", {})).get("is_catalog_proxy"):
                tool_args = request.tool_call.get("args", {})
                if (
                    underlying_name := tool_args.get("tool_name")
                ) and request.runtime.context:
                    if underlying := next(
                        (
                            t
                            for t in request.runtime.context.tool_catalog
                            if t.name == underlying_name
                        ),
                        None,
                    ):
                        actual_tool = underlying
                        tool_name = underlying_name

        # Check if tool is blocked (not in map)
        if tool_name not in self.tool_sandbox_map:
            return None, None, True

        backend = self.tool_sandbox_map[tool_name]
        return backend, actual_tool, False

    async def awrap_tool_call(
        self, request: ToolCallRequest, handler: Callable
    ) -> ToolMessage | Command:
        """Intercept tool calls and sandbox if configured."""
        backend, actual_tool, is_blocked = self._get_sandbox_info(request)

        if is_blocked:
            tool_name = request.tool_call["name"]
            return create_tool_message(
                result=f"Tool '{tool_name}' blocked: no sandbox pattern matched",
                tool_name=tool_name,
                tool_call_id=str(request.tool_call["id"]),
                is_error=True,
            )

        if not backend:
            return await handler(request)

        # Use underlying tool if catalog proxy, otherwise use the request tool
        tool = actual_tool if actual_tool else request.tool
        if not tool:
            return await handler(request)

        tool_call = request.tool_call
        tool_args = (
            tool_call.get("args", {}).get("tool_args", {})
            if actual_tool
            else tool_call.get("args", {})
        )

        # Get the underlying function - check both func and coroutine attributes
        underlying_func = getattr(tool, "func", None) or getattr(
            tool, "coroutine", None
        )
        module_path = (
            getattr(underlying_func, "__module__", tool.__module__)
            if underlying_func
            else tool.__module__
        )
        func_name = (
            getattr(underlying_func, "__name__", tool.name)
            if underlying_func
            else tool.name
        )

        result = await backend.execute(
            module_path=module_path,
            tool_name=func_name,
            args=tool_args,
            tool_runtime=serialize_runtime(request.runtime),
        )

        if not result.get("success"):
            error_msg = f"Sandbox error: {result.get('error')}"
            if tb := result.get("traceback"):
                error_msg += f"\n\nTraceback:\n{tb}"
            if stderr := result.get("stderr"):
                error_msg += f"\n\nStderr:\n{stderr}"
            return create_tool_message(
                result=error_msg,
                tool_name=tool_call["name"],
                tool_call_id=str(tool_call["id"]),
                is_error=True,
            )

        return create_tool_message(
            result=result.get("content", str(result)),
            tool_name=tool_call["name"],
            tool_call_id=str(tool_call["id"]),
            is_error=False,
            short_content=result.get("short_content"),
        )
