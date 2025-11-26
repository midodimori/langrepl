"""Integration tests for memory file tools."""

from pathlib import Path

import pytest

from src.tools.internal.memory import (
    edit_memory_file,
    list_memory_files,
    read_memory_file,
    write_memory_file,
)
from tests.fixtures.tool_helpers import make_tool_call, run_tool


@pytest.mark.asyncio
async def test_memory_file_workflow(create_test_graph, temp_dir: Path):
    """Test memory file operations through the graph."""
    app = create_test_graph(
        [write_memory_file, read_memory_file, list_memory_files, edit_memory_file],
    )

    # Write memory file
    state = make_tool_call(
        "write_memory_file",
        file_path="notes.txt",
        content="My notes\nLine 2",
    )
    state["files"] = {}
    result = await run_tool(
        app, state, working_dir=str(temp_dir), approval_mode="aggressive"
    )

    # Verify memory file was written to state
    assert "notes.txt" in result["files"]
    assert "My notes" in result["files"]["notes.txt"]


@pytest.mark.asyncio
async def test_memory_file_list(create_test_graph, temp_dir: Path):
    """Test listing memory files through the graph."""
    app = create_test_graph([write_memory_file, list_memory_files])

    # First write some files
    state = make_tool_call(
        "write_memory_file", file_path="file1.txt", content="Content 1"
    )
    state["files"] = {}
    result = await run_tool(
        app,
        state,
        thread_id="test1",
        working_dir=str(temp_dir),
        approval_mode="aggressive",
    )

    # Now list files
    list_state = make_tool_call("list_memory_files", call_id="call_2")
    list_state["messages"] = result["messages"] + list_state["messages"][1:]
    list_state["files"] = result["files"]

    list_result = await run_tool(
        app,
        list_state,
        thread_id="test1",
        working_dir=str(temp_dir),
        approval_mode="aggressive",
    )

    # Check list output
    tool_messages = [m for m in list_result["messages"] if m.type == "tool"]
    last_tool_msg = tool_messages[-1]
    assert "file1.txt" in last_tool_msg.content


@pytest.mark.asyncio
async def test_read_nonexistent_memory_file(create_test_graph, temp_dir: Path):
    """Test reading a non-existent memory file."""
    app = create_test_graph([read_memory_file])

    state = make_tool_call("read_memory_file", file_path="nonexistent.txt")
    state["files"] = {}
    result = await run_tool(
        app, state, working_dir=str(temp_dir), approval_mode="aggressive"
    )

    # Check that error message is returned
    tool_messages = [m for m in result["messages"] if m.type == "tool"]
    assert tool_messages
    assert "not found" in tool_messages[0].content.lower()
