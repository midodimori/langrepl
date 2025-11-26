"""Integration tests for file system tools."""

from pathlib import Path

import pytest

from src.tools.impl.file_system import (
    MoveOperation,
    create_dir,
    delete_dir,
    delete_file,
    insert_at_line,
    move_file,
    move_multiple_files,
    read_file,
    write_file,
)
from tests.fixtures.tool_helpers import make_tool_call, run_tool


@pytest.mark.asyncio
async def test_write_and_read_file(create_test_graph, agent_context, temp_dir: Path):
    """Test writing and reading a file through the graph."""
    app = create_test_graph([write_file, read_file])

    state = make_tool_call("write_file", file_path="test.txt", content="Hello World")
    await run_tool(app, state, agent_context)

    assert (temp_dir / "test.txt").exists()
    assert (temp_dir / "test.txt").read_text() == "Hello World"


@pytest.mark.asyncio
async def test_create_and_delete_dir(create_test_graph, agent_context, temp_dir: Path):
    """Test creating and deleting directories through the graph."""
    app = create_test_graph([create_dir, delete_dir])

    state = make_tool_call("create_dir", dir_path="test_dir")
    await run_tool(app, state, agent_context)
    assert (temp_dir / "test_dir").is_dir()

    state = make_tool_call("delete_dir", dir_path="test_dir")
    await run_tool(app, state, agent_context)
    assert not (temp_dir / "test_dir").exists()


@pytest.mark.asyncio
async def test_delete_file(create_test_graph, agent_context, temp_dir: Path):
    """Test deleting a file through the graph."""
    # Setup: create file
    (temp_dir / "delete_me.txt").write_text("content")

    app = create_test_graph([delete_file])

    state = make_tool_call("delete_file", file_path="delete_me.txt")
    await run_tool(app, state, agent_context)

    assert not (temp_dir / "delete_me.txt").exists()


@pytest.mark.asyncio
async def test_insert_at_line(create_test_graph, agent_context, temp_dir: Path):
    """Test inserting content at a specific line through the graph."""
    # Setup: create file with content
    (temp_dir / "insert.txt").write_text("line 1\nline 2\nline 3\n")

    app = create_test_graph([insert_at_line])

    state = make_tool_call(
        "insert_at_line",
        file_path="insert.txt",
        line_number=2,
        content="inserted line",
    )
    await run_tool(app, state, agent_context)

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

    state = make_tool_call(
        "move_file", source_path="source.txt", destination_path="destination.txt"
    )
    await run_tool(app, state, agent_context)

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

    state = make_tool_call(
        "move_multiple_files",
        moves=[
            MoveOperation(source="file1.txt", destination="moved1.txt"),
            MoveOperation(source="file2.txt", destination="moved2.txt"),
        ],
    )
    await run_tool(app, state, agent_context)

    assert not (temp_dir / "file1.txt").exists()
    assert not (temp_dir / "file2.txt").exists()
    assert (temp_dir / "moved1.txt").exists()
    assert (temp_dir / "moved2.txt").exists()
    assert (temp_dir / "moved1.txt").read_text() == "content1"
    assert (temp_dir / "moved2.txt").read_text() == "content2"
