from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore

from src.agents import StateSchemaType
from src.agents.react_agent import create_react_agent
from src.tools.subagents.task import SubAgent, create_task_tool


def create_deep_agent(
    tools: list[BaseTool],
    prompt: str,
    model: BaseChatModel,
    subagents: list[SubAgent] | None = None,
    state_schema: StateSchemaType | None = None,
    context_schema: type[Any] | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    internal_tools: list[BaseTool] | None = None,
    store: BaseStore | None = None,
    name: str | None = None,
) -> CompiledStateGraph:

    all_tools = (internal_tools or []) + tools
    if subagents:
        task_tool = create_task_tool(
            subagents,
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
