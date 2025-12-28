"""Sandbox worker - runs inside the sandboxed environment.

This script is executed inside a sandbox (bubblewrap/seatbelt)
and handles tool execution requests via stdin/stdout JSON protocol.
"""

import asyncio
import importlib
import json
import signal
import sys
import traceback
from dataclasses import asdict
from typing import Any

from langchain_core.messages import ToolMessage
from langgraph.types import Command

from langrepl.sandboxes.constants import ALLOWED_MODULE_PREFIX
from langrepl.sandboxes.serialization import deserialize_runtime


def serialize_result(result: Any) -> dict:
    """Serialize tool result to JSON-compatible format."""
    if isinstance(result, Command):
        return {"success": True, "is_command": True, **asdict(result)}
    if isinstance(result, ToolMessage):
        return {
            "success": True,
            "content": result.content,
            "name": result.name,
            "status": result.status,
            **{
                k: getattr(result, k, None)
                for k in ("short_content", "is_error", "return_direct")
            },
        }
    return {"success": True, "content": str(result)}


async def run(
    module_path: str, tool_name: str, args: dict, tool_runtime: dict | None = None
) -> dict:
    """Run a LangChain tool asynchronously and return serialized result."""
    if not module_path.startswith(ALLOWED_MODULE_PREFIX):
        return {
            "success": False,
            "error": f"Module '{module_path}' not in allowed prefix",
        }

    try:
        tool = getattr(importlib.import_module(module_path), tool_name)

        if not hasattr(tool, "ainvoke"):
            return {
                "success": False,
                "error": f"Tool {tool_name} is not a LangChain tool",
            }

        # Inject runtime if tool requires it
        if tool_runtime and hasattr(tool, "args_schema") and tool.args_schema:
            if (
                "runtime" in getattr(tool.args_schema, "model_fields", {})
                and "runtime" not in args
            ):
                args = {**args, "runtime": deserialize_runtime(tool_runtime)}

        return serialize_result(await tool.ainvoke(args))

    except Exception as e:
        tb = traceback.format_exc()
        sys.stderr.write(f"Error: {e}\n{tb}\n")
        sys.stderr.flush()
        return {"success": False, "error": str(e), "traceback": tb}


def main() -> None:
    """Main entry point for the sandbox worker."""
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))

    try:
        request = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    if not (module_path := request.get("module")) or not (
        tool_name := request.get("tool_name")
    ):
        print(json.dumps({"success": False, "error": "Missing module or tool_name"}))
        sys.exit(1)

    result = asyncio.run(
        run(
            module_path, tool_name, request.get("args", {}), request.get("tool_runtime")
        )
    )
    print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
