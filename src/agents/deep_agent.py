from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from src.agents.react_agent import create_react_agent
from src.tools.subagents.task import SubAgent, create_task_tool

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.tools import BaseTool
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph
    from langgraph.store.base import BaseStore

    from src.agents import StateSchemaType
    from src.core.config import LLMConfig


def create_deep_agent(
    tools: list[BaseTool],
    prompt: str,
    llm_config: LLMConfig,
    model_provider: Callable[[LLMConfig], BaseChatModel],
    subagents: list[SubAgent] | None = None,
    state_schema: StateSchemaType | None = None,
    context_schema: type[Any] | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    internal_tools: list[BaseTool] | None = None,
    store: BaseStore | None = None,
    name: str | None = None,
) -> CompiledStateGraph:

    model = model_provider(llm_config)
    all_tools = (internal_tools or []) + tools
    if subagents:
        task_tool = create_task_tool(
            subagents,
            model_provider,
            state_schema,
        )
        all_tools = all_tools + [task_tool]

    return create_react_agent(
        model,
        prompt=prompt,
        tools=all_tools,
        state_schema=state_schema,
        context_schema=context_schema,
        checkpointer=checkpointer,
        store=store,
        name=name,
    )
