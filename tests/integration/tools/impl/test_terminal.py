"""Integration tests for terminal tools."""

from pathlib import Path

import pytest

from src.tools.impl.terminal import get_directory_structure, run_command
from tests.fixtures.tool_helpers import make_tool_call, run_tool


@pytest.mark.asyncio
async def test_run_command(create_test_graph, agent_context):
    """Test running a command through the graph."""
    app = create_test_graph([run_command])

    state = make_tool_call("run_command", command="echo hello")
    result = await run_tool(app, state, agent_context)

    tool_messages = [m for m in result["messages"] if m.type == "tool"]
    assert tool_messages
    assert "hello" in tool_messages[0].content


@pytest.mark.asyncio
async def test_directory_structure(create_test_graph, agent_context, temp_dir: Path):
    """Test getting directory structure through the graph."""
    (temp_dir / "file1.txt").write_text("content")
    (temp_dir / "subdir").mkdir()

    app = create_test_graph([get_directory_structure])

    state = make_tool_call("get_directory_structure", dir_path=".")
    result = await run_tool(app, state, agent_context)

    tool_messages = [m for m in result["messages"] if m.type == "tool"]
    assert tool_messages
    assert "file1.txt" in tool_messages[0].content


@pytest.mark.asyncio
async def test_run_command_failure(create_test_graph, agent_context):
    """Test running an invalid command through the graph."""
    app = create_test_graph([run_command])

    state = make_tool_call("run_command", command="nonexistent_command_xyz")
    result = await run_tool(app, state, agent_context)

    tool_messages = [m for m in result["messages"] if m.type == "tool"]
    assert tool_messages
    assert (
        "error" in tool_messages[0].content.lower()
        or "not found" in tool_messages[0].content.lower()
    )


@pytest.mark.asyncio
async def test_directory_structure_with_special_chars(
    create_test_graph, agent_context, temp_dir: Path
):
    """Test that directory paths with special characters are properly escaped."""
    special_dir = temp_dir / "dir with spaces"
    special_dir.mkdir()
    (special_dir / "test.txt").write_text("content")

    app = create_test_graph([get_directory_structure])

    state = make_tool_call("get_directory_structure", dir_path=str(special_dir))
    result = await run_tool(app, state, agent_context)

    tool_messages = [m for m in result["messages"] if m.type == "tool"]
    assert tool_messages
    assert "test.txt" in tool_messages[0].content
