from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
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
    store: BaseStore | None = None,
    name: str | None = None,
):
    """
    Create and configure a ReAct-style agent using the provided model, tools, and system prompt.
    
    This assembles middleware for token-cost tracking, tool-approval, optional tool-output compression (if a memory read tool is present), and early return handling, then delegates agent construction to LangChain's create_agent.
    
    Parameters:
        model (BaseChatModel): The chat model used by the agent.
        tools (list[BaseTool]): Tools the agent may invoke.
        prompt (str): The system prompt to seed the agent's behavior.
        state_schema (StateSchemaType | None): Optional schema describing the agent's persistent state.
        context_schema (ContextSchemaType | None): Optional schema describing contextual inputs available to the agent.
        store (BaseStore | None): Optional persistent store for agent state and metadata.
        name (str | None): Optional human-readable name for the agent.
    
    Returns:
        CompiledStateGraph: A configured ReAct agent ready for execution.
    """
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
        store=store,
        name=name,
        middleware=middleware,
    )