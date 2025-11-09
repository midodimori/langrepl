from langchain.tools import ToolRuntime, tool
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, HumanMessage
from langchain_core.tools import BaseTool, ToolException
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict

from src.agents import StateSchemaType
from src.agents.context import AgentContext
from src.agents.react_agent import create_react_agent
from src.agents.state import AgentState
from src.utils.render import create_tool_message


class SubAgent(BaseModel):
    name: str
    description: str
    prompt: str
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
        runtime: ToolRuntime[AgentContext, AgentState],
    ):
        if subagent_type not in agents:
            allowed = [f"`{k}`" for k in agents]
            raise ToolException(
                f"Invoked agent of type {subagent_type}, "
                f"the only allowed types are {allowed}"
            )
        subagent = agents[subagent_type]
        state = runtime.state.copy()
        state["messages"] = [HumanMessage(content=description)]
        result = await subagent.ainvoke(state)

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
