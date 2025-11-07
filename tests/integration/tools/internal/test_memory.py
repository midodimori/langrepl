"""Integration tests for memory file tools."""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.tools.internal.memory import (
    edit_memory_file,
    list_memory_files,
    read_memory_file,
    write_memory_file,
)


@pytest.mark.asyncio
async def test_memory_file_workflow(create_test_graph, temp_dir: Path):
    """Test memory file operations through the graph."""
    app = create_test_graph(
        [write_memory_file, read_memory_file, list_memory_files, edit_memory_file],
    )

    # Write memory file
    initial_state = {
        "messages": [
            HumanMessage(content="Write memory file"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "write_memory_file",
                        "args": {
                            "file_path": "notes.txt",
                            "content": "My notes\nLine 2",
                        },
                    }
                ],
            ),
        ],
        "files": {},
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

    # Verify memory file was written to state
    assert "notes.txt" in result["files"]
    assert "My notes" in result["files"]["notes.txt"]


@pytest.mark.asyncio
async def test_memory_file_list(create_test_graph, temp_dir: Path):
    """Test listing memory files through the graph."""
    app = create_test_graph([write_memory_file, list_memory_files])

    # First write some files
    initial_state = {
        "messages": [
            HumanMessage(content="Setup"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "write_memory_file",
                        "args": {"file_path": "file1.txt", "content": "Content 1"},
                    }
                ],
            ),
        ],
        "files": {},
    }

    result = await app.ainvoke(
        initial_state,
        config={
            "configurable": {
                "thread_id": "test1",
                "working_dir": str(temp_dir),
                "approval_mode": "aggressive",
            }
        },
    )

    # Now list files
    list_state = {
        "messages": result["messages"]
        + [
            AIMessage(
                content="",
                tool_calls=[{"id": "call_2", "name": "list_memory_files", "args": {}}],
            )
        ],
        "files": result["files"],
    }

    list_result = await app.ainvoke(
        list_state,
        config={
            "configurable": {
                "thread_id": "test1",
                "working_dir": str(temp_dir),
                "approval_mode": "aggressive",
            }
        },
    )

    # Check list output
    tool_messages = [m for m in list_result["messages"] if m.type == "tool"]
    last_tool_msg = tool_messages[-1]
    assert "file1.txt" in last_tool_msg.content


@pytest.mark.asyncio
async def test_read_nonexistent_memory_file(create_test_graph, temp_dir: Path):
    """Test reading a non-existent memory file."""
    app = create_test_graph([read_memory_file])

    initial_state = {
        "messages": [
            HumanMessage(content="Read nonexistent file"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "read_memory_file",
                        "args": {"file_path": "nonexistent.txt"},
                    }
                ],
            ),
        ],
        "files": {},
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

    # Check that error message is returned
    tool_messages = [m for m in result["messages"] if m.type == "tool"]
    assert tool_messages
    assert "not found" in tool_messages[0].content.lower()
