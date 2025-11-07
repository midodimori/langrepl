"""Integration tests for file system tools."""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.tools.impl.file_system import (
    create_dir,
    delete_dir,
    delete_file,
    edit_file,
    insert_at_line,
    move_file,
    move_multiple_files,
    read_file,
    write_file,
)


@pytest.mark.asyncio
async def test_write_and_read_file(create_test_graph, agent_context, temp_dir: Path):
    """Test writing and reading a file through the graph."""
    app = create_test_graph([write_file, read_file])

    # Simulate tool call to write file
    initial_state = {
        "messages": [
            HumanMessage(content="Create a file"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "write_file",
                        "args": {"file_path": "test.txt", "content": "Hello World"},
                    }
                ],
            ),
        ],
    }

    result = await app.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": "test"}},
        context=agent_context,
    )

    # Verify file was created
    assert (temp_dir / "test.txt").exists()
    assert (temp_dir / "test.txt").read_text() == "Hello World"


@pytest.mark.asyncio
async def test_edit_file(create_test_graph, agent_context, temp_dir: Path):
    """Test editing a file through the graph."""
    # Setup: create initial file
    (temp_dir / "edit.txt").write_text("line 1\nline 2\nline 3")

    app = create_test_graph([edit_file])

    from src.tools.impl.file_system import EditOperation

    initial_state = {
        "messages": [
            HumanMessage(content="Edit file"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "edit_file",
                        "args": {
                            "file_path": "edit.txt",
                            "edits": [
                                EditOperation(
                                    old_content="line 2", new_content="modified line 2"
                                )
                            ],
                        },
                    }
                ],
            ),
        ],
    }

    result = await app.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": "test"}},
        context=agent_context,
    )

    # Verify edit was applied
    content = (temp_dir / "edit.txt").read_text()
    assert "modified line 2" in content


@pytest.mark.asyncio
async def test_create_and_delete_dir(create_test_graph, agent_context, temp_dir: Path):
    """Test creating and deleting directories through the graph."""
    app = create_test_graph([create_dir, delete_dir])

    # Create directory
    initial_state = {
        "messages": [
            HumanMessage(content="Create directory"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "create_dir",
                        "args": {"dir_path": "test_dir"},
                    }
                ],
            ),
        ],
    }

    result = await app.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": "test"}},
        context=agent_context,
    )

    assert (temp_dir / "test_dir").is_dir()


@pytest.mark.asyncio
async def test_delete_file(create_test_graph, agent_context, temp_dir: Path):
    """Test deleting a file through the graph."""
    # Setup: create file
    (temp_dir / "delete_me.txt").write_text("content")

    app = create_test_graph([delete_file])

    initial_state = {
        "messages": [
            HumanMessage(content="Delete file"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "delete_file",
                        "args": {"file_path": "delete_me.txt"},
                    }
                ],
            ),
        ],
    }

    result = await app.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": "test"}},
        context=agent_context,
    )

    assert not (temp_dir / "delete_me.txt").exists()


@pytest.mark.asyncio
async def test_insert_at_line(create_test_graph, agent_context, temp_dir: Path):
    """Test inserting content at a specific line through the graph."""
    # Setup: create file with content
    (temp_dir / "insert.txt").write_text("line 1\nline 2\nline 3\n")

    app = create_test_graph([insert_at_line])

    initial_state = {
        "messages": [
            HumanMessage(content="Insert line"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "insert_at_line",
                        "args": {
                            "file_path": "insert.txt",
                            "line_number": 2,
                            "content": "inserted line",
                        },
                    }
                ],
            ),
        ],
    }

    result = await app.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": "test"}},
        context=agent_context,
    )

    content = (temp_dir / "insert.txt").read_text()
    assert "inserted line" in content
    lines = content.splitlines()
    assert lines[1] == "inserted line"


@pytest.mark.asyncio
async def test_move_file(create_test_graph, agent_context, temp_dir: Path):
    """Test moving a file through the graph."""
    # Setup: create file
    (temp_dir / "source.txt").write_text("content")

    app = create_test_graph([move_file])

    initial_state = {
        "messages": [
            HumanMessage(content="Move file"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "move_file",
                        "args": {
                            "source_path": "source.txt",
                            "destination_path": "destination.txt",
                        },
                    }
                ],
            ),
        ],
    }

    result = await app.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": "test"}},
        context=agent_context,
    )

    assert not (temp_dir / "source.txt").exists()
    assert (temp_dir / "destination.txt").exists()
    assert (temp_dir / "destination.txt").read_text() == "content"


@pytest.mark.asyncio
async def test_move_multiple_files(create_test_graph, agent_context, temp_dir: Path):
    """Test moving multiple files through the graph."""
    # Setup: create files
    (temp_dir / "file1.txt").write_text("content1")
    (temp_dir / "file2.txt").write_text("content2")

    app = create_test_graph([move_multiple_files])

    from src.tools.impl.file_system import MoveOperation

    initial_state = {
        "messages": [
            HumanMessage(content="Move files"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "move_multiple_files",
                        "args": {
                            "moves": [
                                MoveOperation(
                                    source="file1.txt", destination="moved1.txt"
                                ),
                                MoveOperation(
                                    source="file2.txt", destination="moved2.txt"
                                ),
                            ]
                        },
                    }
                ],
            ),
        ],
    }

    result = await app.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": "test"}},
        context=agent_context,
    )

    assert not (temp_dir / "file1.txt").exists()
    assert not (temp_dir / "file2.txt").exists()
    assert (temp_dir / "moved1.txt").exists()
    assert (temp_dir / "moved2.txt").exists()
    assert (temp_dir / "moved1.txt").read_text() == "content1"
    assert (temp_dir / "moved2.txt").read_text() == "content2"
