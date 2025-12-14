"""Sandbox worker - runs inside the sandboxed environment.

This script is executed inside a Docker container (or bubblewrap/seatbelt sandbox)
and handles tool execution requests via stdin/stdout JSON protocol.
"""

import asyncio
import importlib
import json
import sys
import traceback
from typing import Any


def serialize_result(result: Any) -> dict:
    """Serialize tool result to JSON-compatible format.

    Tools return ToolMessage, str, or Command (for graph control flow).
    """
    from langchain_core.messages import ToolMessage
    from langgraph.types import Command

    if isinstance(result, Command):
        from dataclasses import asdict

        return {
            "success": True,
            "is_command": True,
            **asdict(result),  # graph, update, resume, goto
        }
    if isinstance(result, ToolMessage):
        return {
            "success": True,
            "content": result.content,
            "name": result.name,
            "status": result.status,
            "short_content": getattr(result, "short_content", None),
            "is_error": getattr(result, "is_error", False),
            "return_direct": getattr(result, "return_direct", False),
            "artifact": result.artifact,
        }
    return {"success": True, "content": str(result)}


def create_mock_runtime(tool_call_id: str = "sandbox-tool-call"):
    """Create a mock ToolRuntime for sandbox execution."""
    import os
    from pathlib import Path

    from langchain.tools import ToolRuntime
    from langchain_core.runnables import RunnableConfig

    from src.agents.context import AgentContext
    from src.agents.state import AgentState
    from src.configs import ApprovalMode

    # Get working directory from environment variable (set by executor)
    # Use sentinel path when not set - tools will fail deterministically
    # if they try to use working_dir without FILESYSTEM permission
    working_dir_str = os.environ.get(
        "LANGREPL_WORKING_DIR", "/dev/null/no-filesystem-permission"
    )
    working_dir = Path(working_dir_str)

    # Create a minimal AgentContext
    context = AgentContext(
        approval_mode=ApprovalMode.SEMI_ACTIVE,
        working_dir=working_dir,
    )

    # Create minimal state
    state = AgentState(
        messages=[],
        todos=None,
        files=None,
        current_input_tokens=None,
        current_output_tokens=None,
        total_cost=None,
    )

    # Create minimal config
    config = RunnableConfig()

    # Create a no-op stream writer
    async def noop_stream_writer(data):
        pass

    return ToolRuntime(
        state=state,
        context=context,
        config=config,
        stream_writer=noop_stream_writer,
        tool_call_id=tool_call_id,
        store=None,
    )


async def execute_tool_async(module_path: str, tool_name: str, args: dict) -> dict:
    """Execute a tool asynchronously and return serialized result."""
    try:
        # Import the module containing the tool
        module = importlib.import_module(module_path)
        tool = getattr(module, tool_name)

        # Check if the tool requires a 'runtime' parameter
        args_for_invoke = dict(args)
        if hasattr(tool, "args_schema") and tool.args_schema:
            schema_fields = getattr(tool.args_schema, "model_fields", {})
            if "runtime" in schema_fields and "runtime" not in args_for_invoke:
                # Inject mock runtime
                args_for_invoke["runtime"] = create_mock_runtime(
                    tool_call_id=args.get("_tool_call_id", "sandbox-call")
                )

        # Check if it's a LangChain BaseTool (has ainvoke method)
        if hasattr(tool, "ainvoke"):
            # LangChain tool - use ainvoke
            result = await tool.ainvoke(args_for_invoke)
        elif hasattr(tool, "invoke"):
            # Sync LangChain tool
            result = tool.invoke(args_for_invoke)
        elif asyncio.iscoroutinefunction(tool):
            # Regular async function
            result = await tool(**args_for_invoke)
        elif callable(tool):
            # Regular sync function
            result = tool(**args_for_invoke)
        else:
            return {"success": False, "error": f"Cannot find callable for {tool_name}"}

        return serialize_result(result)

    except Exception as e:
        tb = traceback.format_exc()
        sys.stderr.write(f"Error: {e}\n{tb}\n")
        sys.stderr.flush()
        return {
            "success": False,
            "error": str(e),
            "traceback": tb,
        }


def main():
    """Main entry point for the sandbox worker."""
    # Read request from stdin
    request_json = sys.stdin.read()

    try:
        request = json.loads(request_json)
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    module_path = request.get("module")
    tool_name = request.get("tool_name")
    args = request.get("args", {})

    if not module_path or not tool_name:
        print(json.dumps({"success": False, "error": "Missing module or tool_name"}))
        sys.exit(1)

    # Run the async execution
    result = asyncio.run(execute_tool_async(module_path, tool_name, args))

    # Output result as JSON
    print(json.dumps(result))


if __name__ == "__main__":
    main()
