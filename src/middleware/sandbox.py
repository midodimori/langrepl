"""Middleware for executing tools in sandbox environment."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain_core.tools import ToolException
from langgraph.types import Command

from src.agents import AgentState
from src.agents.context import AgentContext
from src.configs import SandboxPermission
from src.core.logging import get_logger
from src.mcp.tool import LazyMCPTool
from src.sandboxes.base import Sandbox
from src.sandboxes.serialization import serialize_runtime
from src.utils.render import create_sandbox_tool_message

logger = get_logger(__name__)


class SandboxMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Middleware to execute tools in a sandbox environment.

    When enabled, intercepts tool calls and routes them through a sandbox
    executor (bubblewrap or seatbelt) for isolated execution.

    The sandbox executor is read from `context.sandbox_executor`. If not set,
    tools are executed normally without sandboxing.

    MCP tools are skipped (they are sandboxed at server startup level).
    """

    @staticmethod
    def _check_permissions(
        executor: Sandbox,
        required_permissions: list[SandboxPermission],
    ) -> list[SandboxPermission]:
        """Check if sandbox grants all required permissions.

        Returns list of missing permissions, empty if all granted.
        """
        return [
            p for p in required_permissions if not executor.config.has_permission(p)
        ]

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Intercept tool call and execute in sandbox if enabled."""
        tool = request.tool
        if tool is None:
            return await handler(request)

        # Get context and check if sandbox is enabled
        runtime = request.runtime
        if runtime.context is None:
            return await handler(request)

        # Get sandbox executor from context - if not set, execute normally
        executor = runtime.context.sandbox_executor
        if executor is None:
            return await handler(request)

        # Get tool metadata for permission checking
        metadata = tool.metadata or {}

        # Check if tool's required permissions are granted by sandbox
        required_permissions: list[SandboxPermission] = metadata.get(
            "sandbox_permissions", []
        )

        # Deny-by-default: if sandbox is active and tool has no declared permissions,
        # block it (security-first approach - undeclared tools cannot run in sandbox)
        if not required_permissions and not metadata.get("sandbox_bypass"):
            raise ToolException(
                f"Tool '{tool.name}' has no declared sandbox_permissions and cannot "
                "run in sandbox mode."
            )

        missing = self._check_permissions(executor, required_permissions)
        if missing:
            missing_str = ", ".join(p.value for p in missing)
            raise ToolException(
                f"Tool '{tool.name}' requires permissions not granted by sandbox: {missing_str}"
            )

        # MCP tools are sandboxed at server startup level, not per-call
        # Permission check above ensures server has required permissions
        if isinstance(tool, LazyMCPTool):
            logger.debug(f"MCP tool {tool.name} permissions validated, executing")
            return await handler(request)

        # Check for explicit sandbox bypass flag
        if metadata.get("sandbox_bypass"):
            logger.debug(f"Tool {tool.name} bypasses sandbox (sandbox_bypass=True)")
            return await handler(request)

        # Derive module path from tool's underlying function
        func = getattr(tool, "func", None) or getattr(tool, "coroutine", None)
        if not func:
            # Deny-by-default: block tools that can't be sandboxed
            raise ToolException(
                f"Tool '{tool.name}' cannot be sandboxed (no func/coroutine). "
                "Add sandbox_bypass=True to metadata if this tool is safe to run unsandboxed."
            )

        module_path = func.__module__
        logger.debug(f"Executing {tool.name} in sandbox (module: {module_path})")

        result = await executor.execute(
            module_path=module_path,
            tool_name=tool.name,
            args=request.tool_call["args"],
            timeout=executor.config.timeout,
            tool_permissions=required_permissions,
            runtime_context=serialize_runtime(request.runtime),
        )

        return create_sandbox_tool_message(
            result, tool.name, request.tool_call["id"] or ""
        )
