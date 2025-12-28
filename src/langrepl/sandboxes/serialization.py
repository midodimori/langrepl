"""Serialization utilities for sandbox runtime context."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any, cast

from langchain.tools import ToolRuntime
from langchain_core.runnables import RunnableConfig

from langrepl.agents.context import AgentContext


def serialize_runtime(runtime: ToolRuntime) -> dict[str, Any]:
    """Serialize ToolRuntime for sandbox execution (excludes messages, callbacks)."""
    state = runtime.state if isinstance(runtime.state, dict) else vars(runtime.state)
    state_data = {k: v for k, v in state.items() if k != "messages"}

    # Handle todos serialization
    if todos := state_data.get("todos"):
        state_data["todos"] = [
            t.model_dump() if hasattr(t, "model_dump") else dict(t) for t in todos
        ]

    config_data = dict(runtime.config)
    if run_id := config_data.get("run_id"):
        config_data["run_id"] = str(run_id)
    config_data.pop("callbacks", None)

    return {
        "tool_call_id": runtime.tool_call_id or "",
        "state": state_data,
        "context": runtime.context.model_dump(mode="json") if runtime.context else {},
        "config": config_data,
    }


def deserialize_runtime(data: dict[str, Any]) -> ToolRuntime:
    """Reconstruct ToolRuntime from serialized dict."""
    config_data = data.get("config", {})
    config: RunnableConfig = {
        "tags": config_data.get("tags", []),
        "metadata": config_data.get("metadata", {}),
        "recursion_limit": config_data.get("recursion_limit", 25),
        "configurable": config_data.get("configurable", {}),
    }
    if run_name := config_data.get("run_name"):
        config["run_name"] = run_name
    if run_id := config_data.get("run_id"):
        config["run_id"] = uuid.UUID(run_id) if isinstance(run_id, str) else run_id

    context_data = data.get("context")
    context = AgentContext.model_validate(context_data) if context_data else None

    return ToolRuntime(
        state={"messages": [], **data.get("state", {})},
        context=cast(None, context),
        config=config,
        stream_writer=cast(Callable[[Any], None], lambda _: None),
        tool_call_id=data.get("tool_call_id", ""),
        store=None,
    )
