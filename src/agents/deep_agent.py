from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
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
    internal_tools: list[BaseTool] | None = None,
    store: BaseStore | None = None,
    name: str | None = None,
) -> CompiledStateGraph:

    """
    Assembles the provided tools (optionally including internal tools and a generated task tool from subagents) and creates a React-based agent represented as a CompiledStateGraph.
    
    Parameters:
        tools (list[BaseTool]): Primary tools available to the agent.
        prompt (str): Prompt text used to initialize the agent's behavior.
        model (BaseChatModel): Chat model backing the agent's language capabilities.
        subagents (list[SubAgent] | None): If provided, a task tool is created from these subagents and added to the agent's toolset.
        state_schema (StateSchemaType | None): Schema that defines the agent's state shape.
        context_schema (type[Any] | None): Type used to validate or shape runtime context passed to the agent.
        internal_tools (list[BaseTool] | None): Additional tools to include before the primary tools.
        store (BaseStore | None): Optional persistence store for the agent's state.
        name (str | None): Optional human-readable name for the agent.
    
    Returns:
        CompiledStateGraph: The configured React-based agent as a compiled state graph.
    """
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
        store=store,
        name=name,
    )