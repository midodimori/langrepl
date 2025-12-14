"""Sandbox worker - runs inside the sandboxed environment.

This script is executed inside a Docker container (or bubblewrap/seatbelt sandbox)
and handles tool execution requests via stdin/stdout JSON protocol.
"""

import asyncio
import importlib
import json
import sys
import traceback
from dataclasses import asdict
from typing import Any

from langchain_core.messages import ToolMessage
from langgraph.types import Command

from src.sandboxes.serialization import deserialize_runtime


def serialize_result(result: Any) -> dict:
    """Serialize tool result to JSON-compatible format.

    Tools return ToolMessage, str, or Command (for graph control flow).
    """
    if isinstance(result, Command):
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


async def execute_tool_async(
    module_path: str, tool_name: str, args: dict, runtime_context: dict | None = None
) -> dict:
    """Execute a LangChain tool asynchronously and return serialized result.

    All sandboxed tools are @tool decorated, so they always have ainvoke.
    """
    try:
        # Import the module containing the tool
        module = importlib.import_module(module_path)
        tool = getattr(module, tool_name)

        if not hasattr(tool, "ainvoke"):
            return {
                "success": False,
                "error": f"Tool {tool_name} is not a LangChain tool",
            }

        # Build args for invoke, injecting runtime if tool schema requires it
        args_for_invoke = dict(args)
        if hasattr(tool, "args_schema") and tool.args_schema:
            schema_fields = getattr(tool.args_schema, "model_fields", {})
            if "runtime" in schema_fields and "runtime" not in args_for_invoke:
                if runtime_context:
                    args_for_invoke["runtime"] = deserialize_runtime(runtime_context)
                else:
                    return {
                        "success": False,
                        "error": "Tool requires runtime but no runtime_context provided",
                    }

        result = await tool.ainvoke(args_for_invoke)
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
    runtime_context = request.get("runtime_context")

    if not module_path or not tool_name:
        print(json.dumps({"success": False, "error": "Missing module or tool_name"}))
        sys.exit(1)

    # Run the async execution
    result = asyncio.run(
        execute_tool_async(module_path, tool_name, args, runtime_context)
    )

    # Output result as JSON
    print(json.dumps(result))


if __name__ == "__main__":
    main()
