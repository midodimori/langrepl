from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import AnyMessage, HumanMessage
from langchain_core.tools import BaseTool, ToolException
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field

from src.agents import StateSchemaType
from src.agents.context import AgentContext
from src.agents.react_agent import create_react_agent
from src.agents.state import AgentState
from src.core.config import SubAgentConfig
from src.skills.factory import Skill
from src.utils.render import create_tool_message

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langgraph.graph.state import CompiledStateGraph

    from src.core.config import LLMConfig


class SubAgent(BaseModel):
    config: SubAgentConfig
    prompt: str
    tools: list[BaseTool]
    internal_tools: list[BaseTool]
    tools_in_catalog: list[BaseTool] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def description(self) -> str:
        return self.config.description


def create_task_tool(
    subagents: list[SubAgent],
    model_provider: Callable[[LLMConfig], BaseChatModel],
    state_schema: StateSchemaType | None = None,
):
    agents: dict[str, CompiledStateGraph] = {}

    subagent_catalogs = {
        subagent.name: subagent.tools_in_catalog for subagent in subagents
    }

    subagent_skill_catalogs = {subagent.name: subagent.skills for subagent in subagents}

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
        runtime: ToolRuntime[AgentContext, AgentState],
    ):
        valid_names = {sa.name for sa in subagents}
        if subagent_type not in valid_names:
            allowed = [f"`{k}`" for k in valid_names]
            raise ToolException(
                f"Invoked agent of type {subagent_type}, "
                f"the only allowed types are {allowed}"
            )
        if subagent_type not in agents:
            subagent_obj = next(sa for sa in subagents if sa.name == subagent_type)
            model = model_provider(subagent_obj.config.llm)
            agents[subagent_type] = create_react_agent(
                name=subagent_obj.name,
                model=model,
                prompt=subagent_obj.prompt,
                tools=subagent_obj.tools + subagent_obj.internal_tools + [think],
                state_schema=state_schema,
            )
        subagent = agents[subagent_type]
        subagent_obj = next(sa for sa in subagents if sa.name == subagent_type)
        state = runtime.state.copy()
        state["messages"] = [HumanMessage(content=description)]

        context = None
        if runtime.context:
            context = runtime.context.model_copy(deep=True)
            if subagent_type in subagent_catalogs:
                context.tool_catalog = subagent_catalogs[subagent_type]
            if subagent_type in subagent_skill_catalogs:
                context.skill_catalog = subagent_skill_catalogs[subagent_type]
            if subagent_obj.config.tools:
                context.tool_output_max_tokens = (
                    subagent_obj.config.tools.output_max_tokens
                )

        result = await subagent.ainvoke(state, context=context)  # type: ignore

        last_message: AnyMessage = result["messages"][-1]
        final_message = create_tool_message(
            result=last_message,
            tool_name=task.name,
            tool_call_id=runtime.tool_call_id or "",
        )

        is_error = (
            getattr(final_message, "is_error", False)
            or getattr(final_message, "status", None) == "error"
        )

        status = "completed" if not is_error else "failed"
        short_content = (
            getattr(final_message, "short_content", None)
            if not is_error
            else final_message.text
        )
        setattr(
            final_message,
            "short_content",
            (f"Task {status}: {short_content}" if short_content else f"Task {status}"),
        )

        return Command(
            update={
                "files": result.get("files", {}),
                "messages": [final_message],
            }
        )

    task.metadata = {"approval_config": {"always_approve": True}}

    return task


@tool(return_direct=True)
def think(reflection: str) -> str:
    """Tool for strategic reflection on progress and decision-making.

    Always use this tool after each search to analyze results and plan next steps systematically.
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


think.metadata = {"approval_config": {"always_approve": True}}
