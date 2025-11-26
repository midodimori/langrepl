"""Integration tests for todo tools."""

from pathlib import Path

import pytest

from src.agents.state import Todo
from src.tools.internal.todo import read_todos, write_todos
from tests.fixtures.tool_helpers import make_tool_call, run_tool


@pytest.mark.asyncio
async def test_todo_workflow(create_test_graph, temp_dir: Path):
    """Test write and read todos through the graph."""
    app = create_test_graph([write_todos, read_todos])

    todos = [
        Todo(content="Task 1", status="pending"),
        Todo(content="Task 2", status="in_progress"),
    ]

    state = make_tool_call("write_todos", todos=todos)
    result = await run_tool(
        app, state, working_dir=str(temp_dir), approval_mode="aggressive"
    )

    # Verify todos were written to state
    assert result["todos"] is not None
    assert len(result["todos"]) == 2
    assert result["todos"][0]["content"] == "Task 1"
