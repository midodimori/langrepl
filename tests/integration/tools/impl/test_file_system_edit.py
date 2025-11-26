"""Integration tests for edit_file tool."""

from pathlib import Path

import pytest

from src.tools.impl.file_system import EditOperation, edit_file
from tests.fixtures.tool_helpers import make_tool_call, run_tool


@pytest.mark.asyncio
async def test_edit_file(create_test_graph, agent_context, temp_dir: Path):
    """Test editing a file through the graph."""
    (temp_dir / "edit.txt").write_text("line 1\nline 2\nline 3")

    app = create_test_graph([edit_file])

    state = make_tool_call(
        "edit_file",
        file_path="edit.txt",
        edits=[EditOperation(old_content="line 2", new_content="modified line 2")],
    )
    await run_tool(app, state, agent_context)

    content = (temp_dir / "edit.txt").read_text()
    assert "modified line 2" in content


@pytest.mark.asyncio
async def test_edit_file_with_json_string(
    create_test_graph, agent_context, temp_dir: Path
):
    """Test editing a file when edits are passed as JSON string (LLM bug workaround)."""
    (temp_dir / "edit_json.txt").write_text("line 1\nline 2\nline 3")

    app = create_test_graph([edit_file])

    state = make_tool_call(
        "edit_file",
        file_path="edit_json.txt",
        edits='[{"old_content": "line 2", "new_content": "modified line 2"}]',
    )
    await run_tool(app, state, agent_context)

    content = (temp_dir / "edit_json.txt").read_text()
    assert content == "line 1\nmodified line 2\nline 3"


@pytest.mark.asyncio
async def test_edit_file_whitespace_normalized(
    create_test_graph, agent_context, temp_dir: Path
):
    """Test editing with different absolute indentation but same relative structure."""
    (temp_dir / "whitespace.py").write_text(
        "def foo():\n    if True:\n        print('hello')\n        return 42"
    )

    state = make_tool_call(
        "edit_file",
        "call_1",
        file_path="whitespace.py",
        edits=[
            EditOperation(
                old_content="        if True:\n            print('hello')\n            return 42",
                new_content="        if True:\n            print('world')\n            return 99",
            )
        ],
    )

    await run_tool(create_test_graph([edit_file]), state, agent_context)

    content = (temp_dir / "whitespace.py").read_text()
    assert "print('world')" in content
    assert "return 99" in content


@pytest.mark.asyncio
async def test_edit_file_trailing_whitespace(
    create_test_graph, agent_context, temp_dir: Path
):
    """Test editing with trailing whitespace differences."""
    (temp_dir / "trailing.txt").write_text("line 1  \nline 2\t\nline 3   ")

    state = make_tool_call(
        "edit_file",
        "call_1",
        file_path="trailing.txt",
        edits=[EditOperation(old_content="line 2", new_content="modified line 2")],
    )

    await run_tool(create_test_graph([edit_file]), state, agent_context)
    assert "modified line 2" in (temp_dir / "trailing.txt").read_text()


@pytest.mark.asyncio
async def test_edit_file_crlf_vs_lf(create_test_graph, agent_context, temp_dir: Path):
    """Test editing with different line endings (CRLF vs LF)."""
    (temp_dir / "crlf.txt").write_text("line 1\r\nline 2\r\nline 3\r\n")

    state = make_tool_call(
        "edit_file",
        "call_1",
        file_path="crlf.txt",
        edits=[EditOperation(old_content="line 2", new_content="modified line 2")],
    )

    await run_tool(create_test_graph([edit_file]), state, agent_context)
    assert "modified line 2" in (temp_dir / "crlf.txt").read_text()


@pytest.mark.asyncio
async def test_edit_file_multiple_sequential_edits(
    create_test_graph, agent_context, temp_dir: Path
):
    """Test that multiple sequential edits work correctly with position recalculation."""
    (temp_dir / "sequential.txt").write_text("line 1\nline 2\nline 3\nline 4\n")

    state = make_tool_call(
        "edit_file",
        "call_1",
        file_path="sequential.txt",
        edits=[
            EditOperation(old_content="line 1", new_content="MODIFIED LINE 1"),
            EditOperation(old_content="line 2", new_content="MODIFIED LINE 2"),
            EditOperation(old_content="line 3", new_content="MODIFIED LINE 3"),
        ],
    )

    await run_tool(create_test_graph([edit_file]), state, agent_context)
    content = (temp_dir / "sequential.txt").read_text()
    assert "MODIFIED LINE 1" in content
    assert "MODIFIED LINE 2" in content
    assert "MODIFIED LINE 3" in content
    assert "line 4" in content


@pytest.mark.asyncio
async def test_edit_file_overlapping_edits(
    create_test_graph, agent_context, temp_dir: Path
):
    """Test that overlapping edits are detected and rejected."""

    (temp_dir / "overlap.txt").write_text("0123456789")

    app = create_test_graph([edit_file])

    state = make_tool_call(
        "edit_file",
        "call_1",
        file_path="overlap.txt",
        edits=[
            EditOperation(old_content="234", new_content="ABC"),
            EditOperation(old_content="456", new_content="XYZ"),
        ],
    )

    result = await run_tool(app, state, agent_context)

    messages = result["messages"]
    tool_message = messages[-1]
    assert "Overlapping edits" in tool_message.content


@pytest.mark.asyncio
async def test_adjacent_edits_not_overlapping(
    create_test_graph, agent_context, temp_dir: Path
):
    """Test edits that are adjacent but don't overlap."""
    (temp_dir / "adjacent.txt").write_text("AAABBBCCC")

    app = create_test_graph([edit_file])
    state = make_tool_call(
        "edit_file",
        "call_1",
        file_path="adjacent.txt",
        edits=[
            EditOperation(old_content="AAA", new_content="111"),
            EditOperation(old_content="BBB", new_content="222"),
            EditOperation(old_content="CCC", new_content="333"),
        ],
    )

    await run_tool(app, state, agent_context)
    assert (temp_dir / "adjacent.txt").read_text() == "111222333"


@pytest.mark.asyncio
async def test_edits_out_of_order(create_test_graph, agent_context, temp_dir: Path):
    """Test edits provided in reverse order."""
    (temp_dir / "order.txt").write_text("line1\nline2\nline3\n")

    app = create_test_graph([edit_file])
    state = make_tool_call(
        "edit_file",
        "call_1",
        file_path="order.txt",
        edits=[
            EditOperation(old_content="line3", new_content="THIRD"),
            EditOperation(old_content="line1", new_content="FIRST"),
            EditOperation(old_content="line2", new_content="SECOND"),
        ],
    )

    await run_tool(app, state, agent_context)
    content = (temp_dir / "order.txt").read_text()
    assert "FIRST" in content
    assert "SECOND" in content
    assert "THIRD" in content


@pytest.mark.asyncio
async def test_edit_beginning_and_end(create_test_graph, agent_context, temp_dir: Path):
    """Test edits at file boundaries."""
    (temp_dir / "bounds.txt").write_text("start middle end")

    app = create_test_graph([edit_file])
    state = make_tool_call(
        "edit_file",
        "call_1",
        file_path="bounds.txt",
        edits=[
            EditOperation(old_content="start", new_content="BEGIN"),
            EditOperation(old_content="end", new_content="FINISH"),
        ],
    )

    await run_tool(app, state, agent_context)
    assert (temp_dir / "bounds.txt").read_text() == "BEGIN middle FINISH"


@pytest.mark.asyncio
async def test_delete_content(create_test_graph, agent_context, temp_dir: Path):
    """Test deleting content by replacing with empty string."""
    (temp_dir / "delete.txt").write_text("keep DELETE_ME keep")

    app = create_test_graph([edit_file])
    state = make_tool_call(
        "edit_file",
        "call_1",
        file_path="delete.txt",
        edits=[
            EditOperation(old_content="DELETE_ME ", new_content=""),
        ],
    )

    await run_tool(app, state, agent_context)
    assert (temp_dir / "delete.txt").read_text() == "keep keep"


@pytest.mark.asyncio
async def test_multiple_deletes(create_test_graph, agent_context, temp_dir: Path):
    """Test multiple non-overlapping deletions."""
    (temp_dir / "multi_delete.txt").write_text("keep X delete Y keep")

    app = create_test_graph([edit_file])
    state = make_tool_call(
        "edit_file",
        "call_1",
        file_path="multi_delete.txt",
        edits=[
            EditOperation(old_content=" X", new_content=""),
            EditOperation(old_content=" Y", new_content=""),
        ],
    )

    await run_tool(app, state, agent_context)
    assert (temp_dir / "multi_delete.txt").read_text() == "keep delete keep"


@pytest.mark.asyncio
async def test_unicode_content(create_test_graph, agent_context, temp_dir: Path):
    """Test edits with unicode characters."""
    (temp_dir / "unicode.txt").write_text("Hello 世界 مرحبا")

    app = create_test_graph([edit_file])
    state = make_tool_call(
        "edit_file",
        "call_1",
        file_path="unicode.txt",
        edits=[
            EditOperation(old_content="世界", new_content="🌍"),
        ],
    )

    await run_tool(app, state, agent_context)
    assert (temp_dir / "unicode.txt").read_text() == "Hello 🌍 مرحبا"


@pytest.mark.asyncio
async def test_single_character_edits(create_test_graph, agent_context, temp_dir: Path):
    """Test editing single characters."""
    (temp_dir / "single.txt").write_text("a b c")

    app = create_test_graph([edit_file])
    state = make_tool_call(
        "edit_file",
        "call_1",
        file_path="single.txt",
        edits=[
            EditOperation(old_content="a", new_content="X"),
            EditOperation(old_content="c", new_content="Z"),
        ],
    )

    await run_tool(app, state, agent_context)
    assert (temp_dir / "single.txt").read_text() == "X b Z"


@pytest.mark.asyncio
async def test_newline_handling(create_test_graph, agent_context, temp_dir: Path):
    """Test edits involving newlines."""
    (temp_dir / "newlines.txt").write_text("line1\n\nline3")

    app = create_test_graph([edit_file])
    state = make_tool_call(
        "edit_file",
        "call_1",
        file_path="newlines.txt",
        edits=[
            EditOperation(old_content="\n\n", new_content="\nline2\n"),
        ],
    )

    await run_tool(app, state, agent_context)
    assert (temp_dir / "newlines.txt").read_text() == "line1\nline2\nline3"


@pytest.mark.asyncio
async def test_expand_and_shrink(create_test_graph, agent_context, temp_dir: Path):
    """Test edits that expand and shrink content."""
    (temp_dir / "resize.txt").write_text("a SHORT b")

    app = create_test_graph([edit_file])
    state = make_tool_call(
        "edit_file",
        "call_1",
        file_path="resize.txt",
        edits=[
            EditOperation(old_content="SHORT", new_content="VERY_LONG_REPLACEMENT"),
        ],
    )

    await run_tool(app, state, agent_context)
    assert (temp_dir / "resize.txt").read_text() == "a VERY_LONG_REPLACEMENT b"

    state = make_tool_call(
        "edit_file",
        "call_2",
        file_path="resize.txt",
        edits=[
            EditOperation(old_content="VERY_LONG_REPLACEMENT", new_content="X"),
        ],
    )

    await run_tool(app, state, agent_context)
    assert (temp_dir / "resize.txt").read_text() == "a X b"


@pytest.mark.asyncio
async def test_entire_file_replacement(
    create_test_graph, agent_context, temp_dir: Path
):
    """Test replacing entire file content."""
    (temp_dir / "whole.txt").write_text("old content")

    app = create_test_graph([edit_file])
    state = make_tool_call(
        "edit_file",
        "call_1",
        file_path="whole.txt",
        edits=[
            EditOperation(old_content="old content", new_content="completely new"),
        ],
    )

    await run_tool(app, state, agent_context)
    assert (temp_dir / "whole.txt").read_text() == "completely new"


@pytest.mark.asyncio
async def test_repeated_content_first_match(
    create_test_graph, agent_context, temp_dir: Path
):
    """Test that edits match the first occurrence."""
    (temp_dir / "repeat.txt").write_text("foo bar foo")

    app = create_test_graph([edit_file])
    state = make_tool_call(
        "edit_file",
        "call_1",
        file_path="repeat.txt",
        edits=[
            EditOperation(old_content="foo", new_content="XXX"),
        ],
    )

    await run_tool(app, state, agent_context)
    assert (temp_dir / "repeat.txt").read_text() == "XXX bar foo"


@pytest.mark.asyncio
async def test_edit_file_json_string_trailing_newline(
    create_test_graph, agent_context, temp_dir: Path
):
    """Test JSON string with trailing newline (LLM bug)."""
    (temp_dir / "newline.txt").write_text("line 1\nline 2\nline 3")

    app = create_test_graph([edit_file])

    state = make_tool_call(
        "edit_file",
        file_path="newline.txt",
        edits='[{"old_content": "line 2", "new_content": "modified"}]\n',
    )
    await run_tool(app, state, agent_context)

    assert (temp_dir / "newline.txt").read_text() == "line 1\nmodified\nline 3"


@pytest.mark.asyncio
async def test_edit_file_json_string_with_whitespace(
    create_test_graph, agent_context, temp_dir: Path
):
    """Test JSON string with leading/trailing whitespace."""
    (temp_dir / "whitespace.txt").write_text("foo bar baz")

    app = create_test_graph([edit_file])

    state = make_tool_call(
        "edit_file",
        file_path="whitespace.txt",
        edits='  [{"old_content": "bar", "new_content": "qux"}]  \n\t',
    )
    await run_tool(app, state, agent_context)

    assert (temp_dir / "whitespace.txt").read_text() == "foo qux baz"


@pytest.mark.asyncio
async def test_edit_file_json_string_trailing_comma(
    create_test_graph, agent_context, temp_dir: Path
):
    """Test json-repair fixes trailing comma."""
    (temp_dir / "comma.txt").write_text("hello world")

    app = create_test_graph([edit_file])

    state = make_tool_call(
        "edit_file",
        file_path="comma.txt",
        edits='[{"old_content": "world", "new_content": "universe",}]',
    )
    await run_tool(app, state, agent_context)

    assert (temp_dir / "comma.txt").read_text() == "hello universe"


@pytest.mark.asyncio
async def test_edit_file_json_string_missing_quote(
    create_test_graph, agent_context, temp_dir: Path
):
    """Test json-repair fixes missing closing quote."""
    (temp_dir / "quote.txt").write_text("alpha beta gamma")

    app = create_test_graph([edit_file])

    state = make_tool_call(
        "edit_file",
        file_path="quote.txt",
        edits='[{"old_content": "beta", "new_content": "omega}]',
    )
    await run_tool(app, state, agent_context)

    assert (temp_dir / "quote.txt").read_text() == "alpha omega gamma"
