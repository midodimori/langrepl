"""TODO management tools for task planning and progress tracking.

This module provides tools for creating and managing structured task lists
that enable agents to plan complex workflows and track progress through
multi-step operations.
"""

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from src.agents.context import AgentContext
from src.agents.state import AgentState, Todo


@tool()
def write_todos(
    todos: list[Todo],
    runtime: ToolRuntime[AgentContext, AgentState],
) -> Command:
    """Create and manage structured task lists for tracking progress through complex workflows.

    ## When to Use
    - Multi-step or non-trivial tasks requiring coordination
    - When user provides multiple tasks or explicitly requests todo list
    - Avoid for single, trivial actions unless directed otherwise

    ## Best Practices
    - Only one in_progress task at a time
    - Mark completed immediately when task is fully done
    - Always send the full updated list when making changes
    - Prune irrelevant items to keep list focused

    ## Progress Updates
    - Call write_todos again to change task status or edit content
    - Reflect real-time progress; don't batch completions
    - If blocked, keep in_progress and add new task describing blocker

    Args:
        todos: List of Todo items with content and status

    """
    return Command(
        update={
            "todos": todos,
            "messages": [
                ToolMessage(
                    name=write_todos.name,
                    content=f"Updated todo list to {todos}",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
    )


write_todos.metadata = {"approval_config": {"always_approve": True}}


@tool()
def read_todos(
    runtime: ToolRuntime[AgentContext, AgentState],
) -> str:
    """Read the current TODO list from the agent state.

    This tool allows the agent to retrieve and review the current TODO list
    to stay focused on remaining tasks and track progress through complex workflows.
    """
    todos = runtime.state.get("todos")
    if not todos:
        return "No todos currently in the list."

    result = "Current TODO List:\n"
    for i, todo in enumerate(todos, 1):
        status_emoji = {"pending": "⧖", "in_progress": "⏱", "completed": "✓"}
        emoji = status_emoji.get(todo["status"], "?")
        result += f"{i}. {emoji} {todo['content']} ({todo['status']})\n"

    return result.strip()


read_todos.metadata = {"approval_config": {"always_approve": True}}


TODO_TOOLS = [write_todos, read_todos]
