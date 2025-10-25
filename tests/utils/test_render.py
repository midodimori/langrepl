from src.utils.render import (
    _adjust_diff_line_numbers,
    _find_content_line_number,
    format_tool_response,
    generate_diff,
    render_templates,
    truncate_text,
)


class TestRenderTemplates:
    def test_render_simple_string(self):
        result = render_templates("Hello {name}", {"name": "World"})
        assert result == "Hello World"

    def test_render_dict(self):
        data = {"greeting": "Hello {name}", "count": "{num}"}
        context = {"name": "Alice", "num": "42"}
        result = render_templates(data, context)
        assert result == {"greeting": "Hello Alice", "count": "42"}

    def test_render_nested_dict(self):
        data = {"outer": {"inner": "Value: {val}"}}
        context = {"val": "123"}
        result = render_templates(data, context)
        assert result == {"outer": {"inner": "Value: 123"}}

    def test_render_list(self):
        data = ["Item {a}", "Item {b}"]
        context = {"a": "1", "b": "2"}
        result = render_templates(data, context)
        assert result == ["Item 1", "Item 2"]

    def test_render_missing_key(self):
        result = render_templates("Hello {name}", {})
        assert result == "Hello {name}"

    def test_render_none_context(self):
        result = render_templates("Hello {name}", None)
        assert result == "Hello {name}"

    def test_render_non_string_values(self):
        result = render_templates(123, {"key": "value"})
        assert result == 123


class TestFormatToolResponse:
    def test_format_simple_string(self):
        content, short = format_tool_response("Hello")
        assert content == "Hello"
        assert short is None

    def test_format_list(self):
        content, short = format_tool_response(["item1", "item2", "item3"])
        assert content == "item1\nitem2\nitem3"
        assert short is None

    def test_format_dict(self):
        data = {"key": "value", "num": 42}
        content, short = format_tool_response(data)
        assert '"key": "value"' in content
        assert "42" in content
        assert short is None

    def test_format_none(self):
        content, short = format_tool_response(None)
        assert content == ""
        assert short is None

    def test_format_nested_list_with_none(self):
        content, short = format_tool_response(["item1", None, "item2"])
        assert content == "item1\nitem2"


class TestTruncateText:
    def test_no_truncation_needed(self):
        result = truncate_text("Hello", 10)
        assert result == "Hello"

    def test_truncate_long_text(self):
        result = truncate_text("Hello World", 8)
        assert result == "Hello Wo..."

    def test_exact_length(self):
        result = truncate_text("Hello", 5)
        assert result == "Hello"


class TestFindContentLineNumber:
    def test_find_at_beginning(self):
        full = ["line1", "line2", "line3"]
        content: list[str] = ["line1", "line2"]
        result = _find_content_line_number(full, content)
        assert result == 1

    def test_find_in_middle(self):
        full = ["line1", "line2", "line3", "line4"]
        content = ["line2", "line3"]
        result = _find_content_line_number(full, content)
        assert result == 2

    def test_find_at_end(self):
        full = ["line1", "line2", "line3"]
        content = ["line3"]
        result = _find_content_line_number(full, content)
        assert result == 3

    def test_not_found(self):
        full = ["line1", "line2", "line3"]
        content = ["line4", "line5"]
        result = _find_content_line_number(full, content)
        assert result == 0

    def test_empty_content(self):
        full = ["line1", "line2"]
        content: list[str] = []
        result = _find_content_line_number(full, content)
        assert result == 0


class TestAdjustDiffLineNumbers:
    def test_adjust_single_hunk(self):
        diff_lines = ["@@ -1,2 +1,2 @@", " context", "-old", "+new"]
        result = _adjust_diff_line_numbers(diff_lines, start_line=10)

        assert result[0] == "@@ -10,2 +10,2 @@"
        assert result[1:] == diff_lines[1:]

    def test_adjust_multiple_hunks(self):
        diff_lines = [
            "@@ -1,1 +1,1 @@",
            "-old1",
            "+new1",
            "@@ -5,1 +5,1 @@",
            "-old2",
            "+new2",
        ]
        result = _adjust_diff_line_numbers(diff_lines, start_line=20)

        assert result[0] == "@@ -20,1 +20,1 @@"
        assert result[3] == "@@ -24,1 +24,1 @@"

    def test_no_adjustment_needed(self):
        diff_lines = [" context", "-old", "+new"]
        result = _adjust_diff_line_numbers(diff_lines, start_line=1)
        assert result == diff_lines


class TestGenerateDiff:
    def test_basic_diff(self):
        old = "line1\nline2\nline3"
        new = "line1\nmodified\nline3"
        result = generate_diff(old, new, context_lines=1)

        assert len(result) > 0
        assert any("-line2" in line for line in result)
        assert any("+modified" in line for line in result)

    def test_no_changes(self):
        content = "line1\nline2"
        result = generate_diff(content, content, context_lines=1)
        assert len(result) == 0

    def test_diff_with_full_content(self):
        old = "target line"
        new = "modified line"
        full = "other\ntarget line\nmore"

        result = generate_diff(old, new, context_lines=0, full_content=full)
        assert len(result) > 0
