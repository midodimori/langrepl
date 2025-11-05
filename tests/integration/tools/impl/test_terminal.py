"""Integration tests for terminal tools."""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.tools.impl.terminal import get_directory_structure, run_command


@pytest.mark.asyncio
async def test_run_command(create_test_graph, temp_dir: Path):
    """Test running a command through the graph."""
    app = create_test_graph([run_command])

    initial_state = {
        "messages": [
            HumanMessage(content="Run command"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "run_command",
                        "args": {"command": "echo hello"},
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

    # Check that command output is in messages
    tool_messages = [m for m in result["messages"] if m.type == "tool"]
    assert tool_messages
    assert "hello" in tool_messages[0].content


@pytest.mark.asyncio
async def test_directory_structure(create_test_graph, temp_dir: Path):
    """Test getting directory structure through the graph."""
    # Setup: create some files
    (temp_dir / "file1.txt").write_text("content")
    (temp_dir / "subdir").mkdir()

    app = create_test_graph([get_directory_structure])

    initial_state = {
        "messages": [
            HumanMessage(content="Get structure"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "get_directory_structure",
                        "args": {"dir_path": "."},
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

    tool_messages = [m for m in result["messages"] if m.type == "tool"]
    assert tool_messages
    assert "file1.txt" in tool_messages[0].content


@pytest.mark.asyncio
async def test_run_command_failure(create_test_graph, temp_dir: Path):
    """Test running an invalid command through the graph."""
    app = create_test_graph([run_command])

    initial_state = {
        "messages": [
            HumanMessage(content="Run invalid command"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "run_command",
                        "args": {"command": "nonexistent_command_xyz"},
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

    # Check that error is returned
    tool_messages = [m for m in result["messages"] if m.type == "tool"]
    assert tool_messages
    assert (
        "error" in tool_messages[0].content.lower()
        or "not found" in tool_messages[0].content.lower()
    )
