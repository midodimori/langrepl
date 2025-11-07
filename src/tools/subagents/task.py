from langchain.tools import ToolRuntime, tool
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, ToolException
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict

from src.agents import StateSchemaType
from src.agents.react_agent import create_react_agent
from src.agents.state import AgentState


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
    """
    Create a delegating task tool that routes a textual task description to a named sub-agent and returns that sub-agent's result as a Command.
    
    Parameters:
        subagents (list[SubAgent]): Configurations for each available sub-agent (name, prompt, llm, tools).
        state_schema (StateSchemaType | None): Optional schema used to initialize each sub-agent's state.
    
    Returns:
        task (callable): A tool function with signature (description: str, subagent_type: str, runtime: ToolRuntime[None, AgentState]) that:
            - Validates that `subagent_type` matches one of the provided subagents.
            - Copies `runtime.state`, sets `state["messages"]` to the provided description as a HumanMessage, and invokes the chosen sub-agent with that state.
            - Returns a Command whose `update.files` contains any files from the sub-agent result (empty dict if none) and whose `update.messages` contains a single ToolMessage with:
                - name set to the task tool's name,
                - content set to the last message content from the sub-agent result,
                - tool_call_id taken from `runtime.tool_call_id`.
    """
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
        runtime: ToolRuntime[None, AgentState],
    ):
        """
        Delegate a task description to a named sub-agent and return its result packaged as a Command.
        
        Parameters:
        	description (str): The task prompt to send to the chosen sub-agent.
        	subagent_type (str): The name of the sub-agent to invoke; must be one of the registered agent keys.
        	runtime (ToolRuntime[None, AgentState]): Runtime containing the current agent state and tool call identifier; the function copies and uses runtime.state and runtime.tool_call_id.
        
        Returns:
        	Command: A Command whose `update` contains:
        		- files: mapping of files returned by the sub-agent (empty dict if none).
        		- messages: a single ToolMessage named for this task, containing the sub-agent's final message content and the runtime's tool_call_id.
        
        Raises:
        	ToolException: If `subagent_type` is not a known/registered sub-agent.
        """
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
        return Command(
            update={
                "files": result.get("files", {}),
                "messages": [
                    ToolMessage(
                        name=task.name,
                        content=result["messages"][-1].content,
                        tool_call_id=runtime.tool_call_id,
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