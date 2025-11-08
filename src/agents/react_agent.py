from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore

from src.agents import ContextSchemaType, StateSchemaType
from src.middleware import (
    ApprovalMiddleware,
    CompressToolOutputMiddleware,
    ReturnDirectMiddleware,
    TokenCostMiddleware,
)
from src.tools.internal.memory import read_memory_file


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
    # Check if read_memory_file is available for compression
    has_read_memory = read_memory_file in tools

    # Middleware execution order:
    # - before_* hooks: First to last
    # - after_* hooks: Last to first (reverse)
    # - wrap_* hooks: Nested (first middleware wraps all others)

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

    # Group 3: beforeModel - Before each model call
    before_model: list[AgentMiddleware[Any, Any]] = [
        ReturnDirectMiddleware(),  # Check for return_direct and terminate if needed
    ]

    # Combine all middleware
    middleware: list[AgentMiddleware[Any, Any]] = (
        after_model + wrap_tool_call + before_model
    )

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=prompt,
        state_schema=state_schema,
        context_schema=context_schema,
        checkpointer=checkpointer,
        store=store,
        name=name,
        middleware=middleware,
    )
