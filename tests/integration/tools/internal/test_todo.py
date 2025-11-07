"""Integration tests for todo tools."""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.state import Todo
from src.tools.internal.todo import read_todos, write_todos


@pytest.mark.asyncio
async def test_todo_workflow(create_test_graph, temp_dir: Path):
    """Test write and read todos through the graph."""
    app = create_test_graph([write_todos, read_todos])

    # Write todos
    todos = [
        Todo(content="Task 1", status="pending"),
        Todo(content="Task 2", status="in_progress"),
    ]

    initial_state = {
        "messages": [
            HumanMessage(content="Write todos"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "write_todos",
                        "args": {"todos": todos},
                    }
                ],
            ),
        ],
    }

    result = await app.ainvoke(
        initial_state,
        config={
            "configurable": {
                "thread_id": "test",
                "working_dir": str(temp_dir),
                "approval_mode": "aggressive",
            }
        },
    )

    # Verify todos were written to state
    assert result["todos"] is not None
    assert len(result["todos"]) == 2
    assert result["todos"][0]["content"] == "Task 1"
