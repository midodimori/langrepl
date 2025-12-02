from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain.agents import create_agent

from src.middleware import (
    ApprovalMiddleware,
    CompressToolOutputMiddleware,
    PendingToolResultMiddleware,
    ReturnDirectMiddleware,
    TokenCostMiddleware,
    create_dynamic_prompt_middleware,
)
from src.tools.internal.memory import read_memory_file

if TYPE_CHECKING:
    from langchain.agents.middleware import AgentMiddleware
    from langchain_core.language_models import BaseChatModel
    from langchain_core.tools import BaseTool
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.store.base import BaseStore

    from src.agents import ContextSchemaType, StateSchemaType


def create_react_agent(
    model: BaseChatModel,
    tools: list[BaseTool],
    prompt: str,
    state_schema: StateSchemaType | None = None,
    context_schema: ContextSchemaType | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
    name: str | None = None,
):
    """Create a ReAct agent using LangChain's create_agent."""
    has_read_memory = read_memory_file in tools

    # Middleware execution order:
    # - before_* hooks: First to last
    # - after_* hooks: Last to first (reverse)
    # - wrap_* hooks: Nested (first middleware wraps all others)

    # Group 0: Dynamic prompt - Render template with runtime context
    dynamic_prompt: list[AgentMiddleware[Any, Any]] = [
        create_dynamic_prompt_middleware(prompt),
    ]

    # Group 1: afterModel - After each model response
    after_model: list[AgentMiddleware[Any, Any]] = [
        TokenCostMiddleware(),  # Extract token usage and calculate costs
    ]

    # Group 2: wrapToolCall - Around each tool call
    wrap_tool_call: list[AgentMiddleware[Any, Any]] = [
        ApprovalMiddleware(),  # Check approval before executing tools
    ]
    if has_read_memory:
        wrap_tool_call.append(
            CompressToolOutputMiddleware(model)  # Compress large tool outputs
        )

    # Group 3: beforeAgent - Before each agent invocation
    before_agent: list[AgentMiddleware[Any, Any]] = [
        PendingToolResultMiddleware(),  # Repair missing tool results after interrupts
    ]

    # Group 4: beforeModel - Before each model call
    before_model: list[AgentMiddleware[Any, Any]] = [
        ReturnDirectMiddleware(),  # Check for return_direct and terminate if needed
    ]

    # Combine all middleware
    middleware: list[AgentMiddleware[Any, Any]] = (
        dynamic_prompt + after_model + wrap_tool_call + before_agent + before_model
    )

    return create_agent(
        model=model,
        tools=tools,
        state_schema=state_schema,
        context_schema=context_schema,
        checkpointer=checkpointer,
        store=store,
        name=name,
        middleware=middleware,
    )
