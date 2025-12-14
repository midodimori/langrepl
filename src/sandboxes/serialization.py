"""Serialization utilities for sandbox runtime context.

This module provides functions to serialize and deserialize ToolRuntime
components across the sandbox process boundary.

We serialize:
- tool_call_id: str
- state: AgentState (without messages for performance)
- context: AgentContext (without excludes like tool_catalog)
- config: RunnableConfig (without callbacks)

We skip:
- callbacks: Functions cannot be serialized
- stream_writer: Process-specific handle
- store: Would require IPC bridge
- messages: Skipped for performance (can add later if needed)
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, TypedDict, cast

from langchain.tools import ToolRuntime
from langchain_core.runnables import RunnableConfig

from src.agents.context import AgentContext
from src.agents.state import AgentState
from src.configs import ApprovalMode


class SerializedState(TypedDict):
    """Serialized AgentState (without messages)."""

    todos: list[dict[str, Any]] | None
    files: dict[str, str] | None
    current_input_tokens: int | None
    current_output_tokens: int | None
    total_cost: float | None


class SerializedContext(TypedDict):
    """Serialized AgentContext (without non-serializable fields)."""

    approval_mode: str  # Enum value
    working_dir: str
    platform: str
    os_version: str
    current_date_time_zoned: str
    user_memory: str
    input_cost_per_mtok: float | None
    output_cost_per_mtok: float | None
    tool_output_max_tokens: int | None


class SerializedConfig(TypedDict):
    """Serialized RunnableConfig (without callbacks)."""

    tags: list[str]
    metadata: dict[str, Any]
    run_name: str | None
    run_id: str | None  # UUID as string
    recursion_limit: int
    configurable: dict[str, Any]


class RuntimeContext(TypedDict):
    """Complete serialized runtime context for sandbox."""

    tool_call_id: str
    state: SerializedState
    context: SerializedContext
    config: SerializedConfig


# ============================================================================
# Serializers (Parent -> Worker)
# ============================================================================


def serialize_state(state: AgentState | dict) -> SerializedState:
    """Serialize AgentState to JSON-compatible dict.

    Excludes messages for performance - most sandboxed tools don't need them.
    """
    if isinstance(state, dict):
        todos_raw = state.get("todos")
        todos_list = (
            [dict(t) for t in todos_raw]
            if todos_raw and isinstance(todos_raw, Iterable)
            else None
        )
        return SerializedState(
            todos=todos_list,
            files=state.get("files"),
            current_input_tokens=state.get("current_input_tokens"),
            current_output_tokens=state.get("current_output_tokens"),
            total_cost=state.get("total_cost"),
        )
    # Handle as typed dict / dataclass
    todos_raw = getattr(state, "todos", None)
    todos_list = (
        [t.model_dump() if hasattr(t, "model_dump") else dict(t) for t in todos_raw]
        if todos_raw and isinstance(todos_raw, Iterable)
        else None
    )
    return SerializedState(
        todos=todos_list,
        files=getattr(state, "files", None),
        current_input_tokens=getattr(state, "current_input_tokens", None),
        current_output_tokens=getattr(state, "current_output_tokens", None),
        total_cost=getattr(state, "total_cost", None),
    )


def serialize_context(context: AgentContext) -> SerializedContext:
    """Serialize AgentContext to JSON-compatible dict.

    Excludes tool_catalog, skill_catalog, sandbox_executor (non-serializable).
    """
    return SerializedContext(
        approval_mode=context.approval_mode.value,
        working_dir=str(context.working_dir),
        platform=context.platform,
        os_version=context.os_version,
        current_date_time_zoned=context.current_date_time_zoned,
        user_memory=context.user_memory,
        input_cost_per_mtok=context.input_cost_per_mtok,
        output_cost_per_mtok=context.output_cost_per_mtok,
        tool_output_max_tokens=context.tool_output_max_tokens,
    )


def serialize_config(config: RunnableConfig) -> SerializedConfig:
    """Serialize RunnableConfig to JSON-compatible dict.

    Excludes callbacks (functions cannot be serialized).
    """
    run_id = config.get("run_id")
    return SerializedConfig(
        tags=config.get("tags", []),
        metadata=config.get("metadata", {}),
        run_name=config.get("run_name"),
        run_id=str(run_id) if run_id else None,
        recursion_limit=config.get("recursion_limit", 25),
        configurable=config.get("configurable", {}),
    )


def serialize_runtime(runtime: ToolRuntime) -> dict[str, Any]:
    """Serialize complete ToolRuntime for sandbox execution.

    Args:
        runtime: The ToolRuntime to serialize

    Returns:
        RuntimeContext dict that can be JSON serialized
    """
    # Handle None context by creating minimal context
    if runtime.context is None:
        context_data = SerializedContext(
            approval_mode="semi-active",
            working_dir="/tmp",
            platform="",
            os_version="",
            current_date_time_zoned="",
            user_memory="",
            input_cost_per_mtok=None,
            output_cost_per_mtok=None,
            tool_output_max_tokens=None,
        )
    else:
        context_data = serialize_context(runtime.context)

    return {
        "tool_call_id": runtime.tool_call_id or "",
        "state": serialize_state(runtime.state),
        "context": context_data,
        "config": serialize_config(runtime.config),
    }


# ============================================================================
# Deserializers (Worker <- Parent)
# ============================================================================


def deserialize_state(data: SerializedState) -> AgentState:
    """Reconstruct AgentState from serialized dict.

    Messages are set to empty list since we don't serialize them.
    """
    return AgentState(
        messages=[],  # Not serialized for performance
        todos=cast(list[Any], data.get("todos")),
        files=data.get("files"),
        current_input_tokens=data.get("current_input_tokens"),
        current_output_tokens=data.get("current_output_tokens"),
        total_cost=data.get("total_cost"),
    )


def deserialize_context(data: SerializedContext) -> AgentContext:
    """Reconstruct AgentContext from serialized dict.

    Non-serializable fields (tool_catalog, skill_catalog, sandbox_executor)
    are set to their defaults.
    """
    return AgentContext(
        approval_mode=ApprovalMode(data["approval_mode"]),
        working_dir=Path(data["working_dir"]),
        platform=data.get("platform", ""),
        os_version=data.get("os_version", ""),
        current_date_time_zoned=data.get("current_date_time_zoned", ""),
        user_memory=data.get("user_memory", ""),
        input_cost_per_mtok=data.get("input_cost_per_mtok"),
        output_cost_per_mtok=data.get("output_cost_per_mtok"),
        tool_output_max_tokens=data.get("tool_output_max_tokens"),
        # Defaults for non-serializable:
        tool_catalog=[],
        skill_catalog=[],
        sandbox_executor=None,
    )


def deserialize_config(data: SerializedConfig) -> RunnableConfig:
    """Reconstruct RunnableConfig from serialized dict.

    Callbacks are not restored (cannot be serialized).
    """
    import uuid

    config: RunnableConfig = {
        "tags": data.get("tags", []),
        "metadata": data.get("metadata", {}),
        "recursion_limit": data.get("recursion_limit", 25),
        "configurable": data.get("configurable", {}),
    }

    run_name = data.get("run_name")
    if run_name:
        config["run_name"] = run_name

    if data.get("run_id"):
        config["run_id"] = uuid.UUID(data["run_id"])

    return config


def deserialize_runtime(data: dict[str, Any]) -> ToolRuntime[None, dict[str, Any]]:
    """Reconstruct complete ToolRuntime from serialized context.

    Args:
        data: The RuntimeContext dict from serialization

    Returns:
        ToolRuntime with reconstructed state, context, config
    """
    from collections.abc import Callable

    def noop_stream_writer(content: Any) -> None:
        """No-op stream writer for sandbox (cannot bridge to parent)."""

    return ToolRuntime(
        state=cast(dict[str, Any], deserialize_state(data["state"])),
        context=cast(None, deserialize_context(data["context"])),
        config=deserialize_config(data["config"]),
        stream_writer=cast(Callable[[Any], None], noop_stream_writer),
        tool_call_id=data["tool_call_id"],
        store=None,
    )
