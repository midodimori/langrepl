"""Integration tests for grep search tools."""

from pathlib import Path

import pytest

from src.tools.impl.grep_search import OutputMode, grep_search
from tests.fixtures.tool_helpers import make_tool_call, run_tool


@pytest.mark.asyncio
async def test_grep_search_content(create_test_graph, agent_context, temp_dir: Path):
    """Test searching for content through the graph."""
    # Setup: create files with searchable content
    (temp_dir / "test1.py").write_text('def hello():\n    print("hello world")\n')
    (temp_dir / "test2.py").write_text('def goodbye():\n    print("goodbye")\n')

    app = create_test_graph([grep_search])

    state = make_tool_call(
        "grep_search",
        search_query="hello",
        directory_path=".",
        output_mode=OutputMode.CONTENT,
    )
    result = await run_tool(app, state, agent_context)

    # Check that search results are in messages
    tool_messages = [m for m in result["messages"] if m.type == "tool"]
    assert tool_messages
    assert "hello" in tool_messages[0].content.lower()


@pytest.mark.asyncio
async def test_grep_search_files(create_test_graph, agent_context, temp_dir: Path):
    """Test searching for filenames through the graph."""
    # Setup: create files
    (temp_dir / "hello_world.py").write_text("pass")
    (temp_dir / "test.py").write_text("pass")

    app = create_test_graph([grep_search])

    state = make_tool_call(
        "grep_search",
        search_query="hello",
        directory_path=".",
        output_mode=OutputMode.FILES,
    )
    result = await run_tool(app, state, agent_context)

    # Check that filename results are in messages
    tool_messages = [m for m in result["messages"] if m.type == "tool"]
    assert tool_messages
    assert "hello_world.py" in tool_messages[0].content


@pytest.mark.asyncio
async def test_grep_search_both(create_test_graph, agent_context, temp_dir: Path):
    """Test searching for both content and filenames through the graph."""
    # Setup: create files
    (temp_dir / "hello_file.py").write_text('print("hello")')
    (temp_dir / "test.py").write_text("def hello(): pass")

    app = create_test_graph([grep_search])

    state = make_tool_call(
        "grep_search",
        search_query="hello",
        directory_path=".",
        output_mode=OutputMode.BOTH,
    )
    result = await run_tool(app, state, agent_context)

    # Check that both content and filename results are in messages
    tool_messages = [m for m in result["messages"] if m.type == "tool"]
    assert tool_messages
    content = tool_messages[0].content
    # Should find both file name and content matches
    assert "hello" in content.lower()


@pytest.mark.asyncio
async def test_grep_search_no_matches(create_test_graph, agent_context, temp_dir: Path):
    """Test searching when no matches are found."""
    # Setup: create files without the search term
    (temp_dir / "test.py").write_text('print("goodbye")')

    app = create_test_graph([grep_search])

    state = make_tool_call(
        "grep_search",
        search_query="nonexistent_string_xyz",
        directory_path=".",
        output_mode=OutputMode.BOTH,
    )
    result = await run_tool(app, state, agent_context)

    # Check that no results message is returned
    tool_messages = [m for m in result["messages"] if m.type == "tool"]
    assert tool_messages
    assert "No results found" in tool_messages[0].content


@pytest.mark.asyncio
async def test_grep_search_special_characters(
    create_test_graph, agent_context, temp_dir: Path
):
    """Test that special characters in search queries are properly escaped."""
    # Setup: create a file
    (temp_dir / "test.py").write_text('print("hello")')

    app = create_test_graph([grep_search])

    # Test with potentially malicious input containing shell metacharacters
    state = make_tool_call(
        "grep_search",
        search_query="test'; echo 'injected",
        directory_path=".",
        output_mode=OutputMode.FILES,
    )
    result = await run_tool(app, state, agent_context)

    # Should complete without executing injected command
    tool_messages = [m for m in result["messages"] if m.type == "tool"]
    assert tool_messages
    assert "No results found" in tool_messages[0].content
