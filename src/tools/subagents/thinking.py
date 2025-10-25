from typing import Annotated

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId, ToolException, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict

from src.agents import StateSchemaType
from src.agents.react_agent import create_react_agent
from src.state.base import BaseState


class SubAgent(BaseModel):
    name: str
    description: str
    prompt: SystemMessage
    llm: BaseChatModel
    tools: list[BaseTool]
    internal_tools: list[BaseTool]

    model_config = ConfigDict(arbitrary_types_allowed=True)


def create_task_tool(
    subagents: list[SubAgent],
    state_schema: StateSchemaType | None = None,
):
    agents = {
        subagent.name: create_react_agent(
            name=subagent.name,
            model=subagent.llm,
            prompt=subagent.prompt,
            tools=subagent.tools + subagent.internal_tools + [think],
            state_schema=state_schema,
        )
        for subagent in subagents
    }

    descriptions = "\n".join(
        f"- {subagent.name}: {subagent.description}" for subagent in subagents
    )

    @tool(
        description=(
            "Delegate a task to a specialized sub-agent with isolated context. "
            f"Available agents for delegation are:\n{descriptions}"
        )
    )
    async def task(
        description: str,
        subagent_type: str,
        state: Annotated[BaseState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ):
        if subagent_type not in agents:
            allowed = [f"`{k}`" for k in agents]
            raise ToolException(
                f"Invoked agent of type {subagent_type}, "
                f"the only allowed types are {allowed}"
            )
        subagent = agents[subagent_type]
        state.messages = [HumanMessage(content=description)]
        result = await subagent.ainvoke(state)
        return Command(
            update={
                "files": result.get("files", {}),
                "messages": [
                    ToolMessage(
                        result["messages"][-1].content, tool_call_id=tool_call_id
                    )
                ],
            }
        )

    return task


@tool(return_direct=True)
def think(reflection: str) -> str:
    """Tool for strategic reflection on progress and decision-making.

    Use this tool after each search to analyze results and plan next steps systematically.
    This creates a deliberate pause in the workflow for quality decision-making.

    When to use:
    - After receiving search results: What key information did I find?
    - Before deciding next steps: Do I have enough to answer comprehensively?
    - When assessing gaps: What specific information am I still missing?
    - Before concluding: Can I provide a complete answer now?
    - How complex is the question: Have I reached the number of search limits?

    Reflection should address:
    1. Analysis of current findings - What concrete information have I gathered?
    2. Gap assessment - What crucial information is still missing?
    3. Quality evaluation - Do I have sufficient evidence/examples for a good answer?
    4. Strategic decision - Should I continue searching or provide my answer?

    Args:
        reflection: Your detailed reflection on progress, findings, gaps, and next steps

    Returns:
        Confirmation that reflection was recorded for decision-making
    """
    return f"Reflection recorded: {reflection}"
