"""TODO management tools for task planning and progress tracking.

This module provides tools for creating and managing structured task lists
that enable agents to plan complex workflows and track progress through
multi-step operations.
"""

from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from src.state.base import BaseState, Todo


@tool()
def write_todos(
    todos: list[Todo], tool_call_id: Annotated[str, InjectedToolCallId]
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
        todos (list[Todo]): List of Todo items with content and status

    """
    return Command(
        update={
            "todos": todos,
            "messages": [
                ToolMessage(f"Updated todo list to {todos}", tool_call_id=tool_call_id)
            ],
        }
    )


@tool()
def read_todos(
    state: Annotated[BaseState, InjectedState],
) -> str:
    """Read the current TODO list from the agent state.

    This tool allows the agent to retrieve and review the current TODO list
    to stay focused on remaining tasks and track progress through complex workflows.
    """
    todos = state.todos
    if not todos:
        return "No todos currently in the list."

    result = "Current TODO List:\n"
    for i, todo in enumerate(todos, 1):
        status_emoji = {"pending": "⧖", "in_progress": "⏱", "completed": "✓"}
        emoji = status_emoji.get(todo["status"], "?")
        result += f"{i}. {emoji} {todo['content']} ({todo['status']})\n"

    return result.strip()


TODO_TOOLS = [write_todos, read_todos]
