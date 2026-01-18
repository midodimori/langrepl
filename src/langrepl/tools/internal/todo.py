"""TODO management tools for task planning and progress tracking.

This module provides tools for creating and managing structured task lists
that enable agents to plan complex workflows and track progress through
multi-step operations.
"""

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from rich.markup import escape

from langrepl.agents.context import AgentContext
from langrepl.agents.state import AgentState, Todo
from langrepl.cli.theme import theme


def format_todos(
    todos: list[Todo],
    max_items: int = 10,
    max_completed: int = 2,
    show_completed_indicator: bool = True,
) -> str:
    """Render todos as Rich markup with status indicators and summaries."""

    if not todos:
        return "[muted]No todos[/muted]"

    status_meta: dict[str, tuple[str, str]] = {
        "pending": ("⧖", theme.primary_text),
        "in_progress": ("↻", theme.info_color),
        "completed": ("✓", theme.success_color),
    }

    completed = [t for t in todos if t.get("status") == "completed"]
    active = [t for t in todos if t.get("status") in ("in_progress", "pending")]

    priority = {"in_progress": 0, "pending": 1}
    active_sorted = sorted(
        active,
        key=lambda todo: priority.get(todo.get("status", "pending"), 2),
    )

    lines: list[str] = []
    items_shown = 0

    if show_completed_indicator and len(completed) > max_completed:
        hidden_count = len(completed) - max_completed
        lines.append(f"[{theme.muted_text}]+{hidden_count} more completed[/]")

    completed_to_show = completed[-max_completed:]
    for todo in completed_to_show:
        if items_shown >= max_items:
            break
        icon, color = status_meta["completed"]
        content = escape(todo.get("content", "").strip())
        lines.append(f"[{color}]{icon} {content}[/]")
        items_shown += 1

    active_shown = 0
    for todo in active_sorted:
        if items_shown >= max_items:
            remaining = len(active_sorted) - active_shown
            if remaining > 0:
                lines.append(f"[{theme.muted_text}]+{remaining} more[/]")
            break
        status = todo.get("status", "pending")
        icon, color = status_meta.get(status, ("•", theme.secondary_text))
        content = escape(todo.get("content", "").strip())
        lines.append(f"[{color}]{icon} {content}[/]")
        items_shown += 1
        active_shown += 1

    return "\n".join(lines)


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
    formatted_todos = format_todos(todos)

    return Command(
        update={
            "todos": todos,
            "messages": [
                ToolMessage(
                    name=write_todos.name,
                    content=f"Updated todo list to {todos}",
                    tool_call_id=runtime.tool_call_id,
                    short_content=formatted_todos,
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

    return format_todos(todos, max_items=50)


read_todos.metadata = {"approval_config": {"always_approve": True}}


TODO_TOOLS = [write_todos, read_todos]
