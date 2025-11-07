"""TODO management tools for task planning and progress tracking.

This module provides tools for creating and managing structured task lists
that enable agents to plan complex workflows and track progress through
multi-step operations.
"""

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from src.agents.state import AgentState, Todo


@tool()
def write_todos(
    todos: list[Todo],
    runtime: ToolRuntime[None, AgentState],
) -> Command:
    """
    Create or replace the agent's TODO list and emit a tool update describing the change.
    
    Sets update.todos to the provided list and includes a single ToolMessage in update.messages whose name is write_todos.name, content describes the updated list, and tool_call_id is taken from runtime.tool_call_id.
    
    Parameters:
        todos (list[Todo]): List of Todo items; each item should include `content` and `status`.
    
    Returns:
        Command: A Command with `update.todos` set to `todos` and `update.messages` containing the single ToolMessage described above.
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


@tool()
def read_todos(
    runtime: ToolRuntime[None, AgentState],
) -> str:
    """
    Read the current TODO list from the agent state.
    
    Returns a human-readable string listing each todo with an index, a status emoji, the todo content, and the status in parentheses; returns "No todos currently in the list." if no todos are present.
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


TODO_TOOLS = [write_todos, read_todos]