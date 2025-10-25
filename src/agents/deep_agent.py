from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore

from src.agents import StateSchemaType
from src.agents.react_agent import create_react_agent
from src.state.base import BaseState
from src.tools.subagents.thinking import SubAgent, create_task_tool


def create_deep_agent(
    tools: list[BaseTool],
    prompt: SystemMessage,
    model: BaseChatModel,
    subagents: list[SubAgent] | None = None,
    state_schema: StateSchemaType | None = None,
    internal_tools: list[BaseTool] | None = None,
    config_schema: type[Any] | None = None,
    store: BaseStore | None = None,
    name: str | None = None,
) -> CompiledStateGraph:
    state_schema = state_schema or BaseState

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
        config_schema=config_schema,
        store=store,
        name=name,
    )
