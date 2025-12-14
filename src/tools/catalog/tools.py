import json
import re

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langchain_core.tools import ToolException
from langgraph.types import Command

from src.agents.context import AgentContext
from src.configs import SandboxPermission
from src.core.logging import get_logger
from src.mcp.tool import LazyMCPTool
from src.tools.schema import ToolSchema
from src.utils.render import create_sandbox_tool_message

logger = get_logger(__name__)


@tool
async def fetch_tools(
    runtime: ToolRuntime[AgentContext], pattern: str | None = None
) -> str:
    """Discover and search for available tools in the catalog.

    This is the PRIMARY tool for finding tools you need. Use this when you need to know what
    tools are available or when looking for tools to accomplish a specific task.

    WITHOUT pattern: Returns ALL available tools (use for browsing/exploring)
    WITH pattern: Returns ONLY matching tools (use when you know what you're looking for)

    The pattern searches BOTH tool names AND descriptions using case-insensitive regex.
    This is much more efficient than listing all tools when you have a specific need.

    Args:
        pattern: Optional regex pattern to filter tools. Common patterns:
            - Simple keyword: "file", "web", "search"
            - Multiple keywords: "read|write|edit"
            - Starts with: "^web"
            - Contains word: "\\bfile\\b"

    Returns:
        Newline-separated list of matching tool names, sorted alphabetically.
        Returns "No tools found matching pattern" if pattern yields no matches.

    When to use:
        - Starting a task: fetch_tools("keyword") to find relevant tools
        - Exploring capabilities: fetch_tools() to see everything available
        - Looking for alternatives: fetch_tools("read|write") to find similar tools
        - Unsure what exists: fetch_tools("web") to discover web-related tools

    Example workflow:
    1. fetch_tools("file") - find file-related tools
    2. get_tool("read_file") - learn how to use a specific tool
    3. run_tool("read_file", {"file_path": "/path"}) - execute it

    Examples:
        fetch_tools() - list all available tools
        fetch_tools("file") - find all file-related tools
        fetch_tools("read|write") - find tools for reading or writing
        fetch_tools("^web") - find tools starting with "web"
        fetch_tools("search") - find all search-related tools
    """
    tools = runtime.context.tool_catalog

    if pattern is None:
        return "\n".join(sorted(t.name for t in tools))

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        raise ToolException(f"Invalid regex pattern: {e}") from e

    matches = []
    for t in tools:
        if regex.search(t.name):
            matches.append(t.name)
        elif t.description and regex.search(t.description):
            matches.append(t.name)

    if not matches:
        return "No tools found matching pattern"

    return "\n".join(sorted(matches))


fetch_tools.metadata = {
    "approval_config": {"always_approve": True},
    "sandbox_bypass": True,
}


@tool
async def get_tool(tool_name: str, runtime: ToolRuntime[AgentContext]) -> str:
    """Learn how to use a specific tool by getting its documentation and parameters.

    Use this after fetch_tools() when you've identified a tool you want to use but need to
    understand its parameters and what it does. Returns detailed JSON with the tool's
    description and input schema (parameter names, types, and descriptions).

    Args:
        tool_name: Name of the tool (get this from fetch_tools() output)

    Returns:
        JSON with: name (str), description (str), parameters (object schema)
    """
    tools = runtime.context.tool_catalog
    tool = next((t for t in tools if t.name == tool_name), None)

    if not tool:
        raise ToolException(f"Tool '{tool_name}' not found")

    schema = ToolSchema.from_tool(tool).model_dump()

    return json.dumps(schema, indent=2)


get_tool.metadata = {
    "approval_config": {"always_approve": True},
    "sandbox_bypass": True,
}


@tool
async def run_tool(
    tool_name: str, tool_args: dict, runtime: ToolRuntime[AgentContext]
) -> str | ToolMessage | Command:
    """Execute a tool from the catalog with the specified arguments.

    Use this after you've called get_tool() to understand the required parameters.
    This is how you actually perform actions using discovered tools.

    Args:
        tool_name: Name of the tool to run (from fetch_tools() output)
        tool_args: Dictionary of arguments matching the tool's input schema (from get_tool())

    Returns:
        The result of the tool execution, which may be a string, ToolMessage, Command.

    Example:
        After get_tool("read_file") shows it needs {"file_path": "..."},
        call run_tool("read_file", {"file_path": "/path/to/file.txt"})
    """
    tools = runtime.context.tool_catalog
    underlying_tool = next((t for t in tools if t.name == tool_name), None)

    if not underlying_tool:
        raise ToolException(f"Tool '{tool_name}' not found")

    executor = runtime.context.sandbox_executor
    metadata = underlying_tool.metadata or {}

    # Check if tool should bypass sandbox
    if executor is not None and not metadata.get("sandbox_bypass"):
        required_permissions: list[SandboxPermission] = metadata.get(
            "sandbox_permissions", []
        )

        # Deny-by-default: if tool has no declared permissions, block it
        if not required_permissions:
            raise ToolException(
                f"Tool '{tool_name}' has no declared sandbox_permissions and cannot "
                "run in sandbox mode."
            )

        missing = [
            p for p in required_permissions if not executor.config.has_permission(p)
        ]
        if missing:
            missing_str = ", ".join(p.value for p in missing)
            raise ToolException(
                f"Tool '{tool_name}' requires permissions not granted by sandbox: {missing_str}"
            )

        # MCP tools are sandboxed at server startup level, not per-call
        if isinstance(underlying_tool, LazyMCPTool):
            pass  # Fall through to normal execution below
        else:
            # For non-MCP tools, execute in sandbox
            func = getattr(underlying_tool, "func", None) or getattr(
                underlying_tool, "coroutine", None
            )
            if not func:
                raise ToolException(
                    f"Tool '{tool_name}' cannot be sandboxed (no func/coroutine). "
                    "Add sandbox_bypass=True to metadata if this tool is safe to run unsandboxed."
                )

            module_path = func.__module__
            logger.debug(f"Executing {tool_name} in sandbox (module: {module_path})")

            result = await executor.execute(
                module_path=module_path,
                tool_name=tool_name,
                args=tool_args,
                timeout=executor.config.timeout,
                tool_permissions=required_permissions,
            )

            return create_sandbox_tool_message(
                result, tool_name, runtime.tool_call_id or ""
            )

    tool_expects_runtime = False
    if underlying_tool.args_schema is not None and hasattr(
        underlying_tool.args_schema, "model_fields"
    ):
        tool_expects_runtime = "runtime" in underlying_tool.args_schema.model_fields

    invoke_args = {**tool_args}
    if tool_expects_runtime:
        invoke_args["runtime"] = runtime

    result = await underlying_tool.ainvoke(invoke_args)

    return result


run_tool.metadata = {
    "approval_config": {
        "is_catalog_proxy": True,
        "underlying_tool_name_arg": "tool_name",
        "underlying_tool_args_arg": "tool_args",
    },
    "sandbox_bypass": True,
}


CATALOG_TOOLS = [fetch_tools, get_tool, run_tool]
