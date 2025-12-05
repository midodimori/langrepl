"""Tests for Renderer critical logic."""

import re

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.cli.ui.markdown import wrap_html_in_code_blocks
from src.cli.ui.renderer import Renderer


class TestRendererThinkingExtraction:
    """Tests for thinking extraction from multiple sources."""

    def test_extract_thinking_from_metadata_bedrock_style(self):
        """Test extracting thinking from metadata (Bedrock pattern)."""
        message = AIMessage(
            content="Main response",
            additional_kwargs={"thinking": {"text": "My reasoning here"}},
        )
        thinking = Renderer._extract_thinking_from_metadata(message)
        assert thinking == "My reasoning here"

    def test_extract_thinking_from_metadata_no_thinking(self):
        """Test extraction returns None when no thinking in metadata."""
        message = AIMessage(content="Main response", additional_kwargs={})
        thinking = Renderer._extract_thinking_from_metadata(message)
        assert thinking is None

    def test_extract_thinking_from_metadata_missing_additional_kwargs(self):
        """Test extraction handles missing additional_kwargs gracefully."""
        message = AIMessage(content="Main response")
        if hasattr(message, "additional_kwargs"):
            delattr(message, "additional_kwargs")
        thinking = Renderer._extract_thinking_from_metadata(message)
        assert thinking is None

    def test_extract_thinking_from_content_blocks_thinking_type(self):
        """Test extracting thinking from content blocks with 'thinking' type."""
        blocks: list[dict[str, str]] = [
            {"type": "thinking", "thinking": "My thought process"},
            {"type": "text", "text": "Main response"},
        ]
        texts, thinking = Renderer._extract_thinking_and_text_from_blocks(blocks)  # type: ignore[arg-type]
        assert "My thought process" in thinking
        assert "Main response" in texts[0]

    def test_extract_thinking_from_content_blocks_reasoning_type(self):
        """Test extracting reasoning from content blocks with 'reasoning' type."""
        blocks: list[dict[str, object]] = [
            {
                "type": "reasoning",
                "summary": [
                    {"text": "Step 1: analyze"},
                    {"text": "Step 2: conclude"},
                ],
            },
            {"type": "text", "text": "Final answer"},
        ]
        texts, thinking = Renderer._extract_thinking_and_text_from_blocks(blocks)  # type: ignore[arg-type]
        assert len(thinking) == 1
        assert "Step 1: analyze" in thinking[0]
        assert "Step 2: conclude" in thinking[0]

    def test_extract_thinking_from_content_blocks_reasoning_content_type(self):
        """Test extracting reasoning_content type blocks."""
        blocks: list[dict[str, str]] = [
            {"type": "reasoning_content", "reasoning_content": "Detailed reasoning"},
            {"type": "text", "text": "Answer"},
        ]
        texts, thinking = Renderer._extract_thinking_and_text_from_blocks(blocks)  # type: ignore[arg-type]
        assert "Detailed reasoning" in thinking
        assert "Answer" in texts[0]

    def test_extract_thinking_from_content_blocks_mixed_types(self):
        """Test extracting from mixed content block types."""
        blocks: list[str | dict[str, str]] = [
            "Plain string text\n",
            {"type": "thinking", "thinking": "Thought 1"},
            {"type": "text", "text": "Regular text"},
            {"type": "thinking", "thinking": "Thought 2"},
        ]
        texts, thinking = Renderer._extract_thinking_and_text_from_blocks(blocks)  # type: ignore[arg-type]
        assert len(thinking) == 2
        assert "Thought 1" in thinking
        assert "Thought 2" in thinking
        assert len(texts) == 2

    def test_extract_thinking_from_content_blocks_text_newline_handling(self):
        """Test that text blocks have proper newline handling."""
        blocks: list[dict[str, str]] = [
            {"type": "text", "text": "Line 1"},
            {"type": "text", "text": "Line 2\n"},
        ]
        texts, thinking = Renderer._extract_thinking_and_text_from_blocks(blocks)  # type: ignore[arg-type]
        assert texts[0] == "Line 1\n"
        assert texts[1] == "Line 2\n"

    def test_extract_thinking_tags_at_start_of_content(self):
        """Test extracting XML-style <think> tags at start of content."""
        content = "<think>My reasoning process</think>\nThe actual answer"
        cleaned, thinking = Renderer._extract_thinking_tags(content)
        assert thinking == "My reasoning process"
        assert cleaned == "The actual answer"

    def test_extract_thinking_tags_ignores_mid_content(self):
        """Test that <think> tags mid-content are treated as literal text."""
        content = "The answer is <think>not extracted</think> final"
        cleaned, thinking = Renderer._extract_thinking_tags(content)
        assert thinking is None
        assert cleaned == content

    def test_extract_thinking_tags_multiple_tags_at_start(self):
        """Test extracting multiple <think> tags at content start."""
        content = "<think>Thought 1</think>\n<think>Thought 2</think>\nAnswer"
        cleaned, thinking = Renderer._extract_thinking_tags(content)
        assert thinking is not None
        assert "Thought 1" in thinking
        assert "Thought 2" in thinking
        assert cleaned == "Answer"

    def test_extract_thinking_tags_with_whitespace(self):
        """Test extraction handles leading whitespace before tags."""
        content = "   <think>My reasoning</think>\nAnswer"
        cleaned, thinking = Renderer._extract_thinking_tags(content)
        assert thinking == "My reasoning"
        assert cleaned == "Answer"

    def test_extract_thinking_tags_multiline_content(self):
        """Test extraction of multiline thinking content."""
        content = """<think>
        Line 1 of thinking
        Line 2 of thinking
        </think>
        The answer"""
        cleaned, thinking = Renderer._extract_thinking_tags(content)
        assert thinking is not None
        assert "Line 1 of thinking" in thinking
        assert "Line 2 of thinking" in thinking
        assert "The answer" in cleaned


class TestRendererAssistantMessage:
    """Tests for complex assistant message rendering scenarios."""

    def test_render_assistant_message_with_all_thinking_sources(self):
        """Test rendering message with thinking from metadata, blocks, and XML."""
        message = AIMessage(
            content=[
                {"type": "thinking", "thinking": "Block thinking"},
                {"type": "text", "text": "<think>XML thinking</think>\nMain content"},
            ],
            additional_kwargs={"thinking": {"text": "Metadata thinking"}},
        )

        # Should not raise and should extract all thinking types
        Renderer.render_assistant_message(message)

    def test_render_assistant_message_only_tool_calls_no_content(self):
        """Test rendering message with only tool calls and no content."""
        message = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search",
                    "args": {"query": "test"},
                    "id": "1",
                    "type": "tool_call",
                }
            ],
        )
        # Should not raise
        Renderer.render_assistant_message(message)

    def test_render_assistant_message_empty_content_and_no_tools(self):
        """Test rendering message with no content and no tool calls returns early."""
        message = AIMessage(content="", tool_calls=[])
        # Should not raise and return early
        Renderer.render_assistant_message(message)

    def test_render_assistant_message_is_error_flag(self):
        """Test rendering error messages uses error styling."""
        message = AIMessage(content="Error occurred")
        message.is_error = True  # type: ignore[attr-defined]
        # Should not raise and render as error
        Renderer.render_assistant_message(message)


class TestRendererToolCallFormatting:
    """Tests for tool call formatting edge cases."""

    def test_format_tool_call_with_long_arguments(self):
        """Test that long arguments are truncated with ellipsis."""
        tool_call = {
            "name": "read_file",
            "args": {"path": "a" * 300},
        }
        formatted = Renderer._format_tool_call(tool_call)
        assert "..." in formatted
        assert len(formatted) < 250

    def test_format_tool_call_with_no_arguments(self):
        """Test formatting tool call without arguments."""
        tool_call = {
            "name": "get_time",
            "args": {},
        }
        formatted = Renderer._format_tool_call(tool_call)
        formatted_str = str(formatted)
        assert "⚙ get_time" in formatted_str

    def test_format_tool_call_with_multiple_arguments(self):
        """Test formatting tool call with multiple arguments."""
        tool_call = {
            "name": "search",
            "args": {"query": "test", "limit": 10, "filter": "active"},
        }
        formatted = Renderer._format_tool_call(tool_call)
        formatted_str = str(formatted)
        assert "⚙ search" in formatted_str
        assert "query :" in formatted_str
        assert "limit :" in formatted_str
        assert "filter :" in formatted_str

    def test_format_tool_call_missing_name(self):
        """Test formatting handles missing tool name gracefully."""
        tool_call = {
            "args": {"key": "value"},
        }
        formatted = Renderer._format_tool_call(tool_call)
        formatted_str = str(formatted).lower()
        assert "unknown" in formatted_str or "(" in str(formatted)

    def test_format_tool_call_missing_args(self):
        """Test formatting handles missing args gracefully."""
        tool_call = {
            "name": "tool_name",
        }
        formatted = Renderer._format_tool_call(tool_call)
        formatted_str = str(formatted)
        assert "⚙ tool_name" in formatted_str


class TestRendererToolMessage:
    """Tests for tool message rendering."""

    def test_render_tool_message_with_short_content(self):
        """Test rendering tool message with short content."""
        message = ToolMessage(content="Success", tool_call_id="1")
        # Should add proper indentation
        Renderer.render_tool_message(message)

    def test_render_tool_message_uses_short_content_attribute(self):
        """Test that short_content attribute is preferred over text."""
        message = ToolMessage(content="Very long content " * 100, tool_call_id="1")
        message.short_content = "Truncated"  # type: ignore[attr-defined]
        # Should use short_content
        Renderer.render_tool_message(message)

    def test_render_tool_message_error_status(self):
        """Test rendering tool message with error status."""
        message = ToolMessage(
            content="Error occurred", tool_call_id="1", status="error"
        )
        # Should render with error styling
        Renderer.render_tool_message(message)

    def test_render_tool_message_is_error_flag(self):
        """Test rendering tool message with is_error flag."""
        message = ToolMessage(content="Error", tool_call_id="1")
        message.is_error = True  # type: ignore[attr-defined]
        # Should render with error styling
        Renderer.render_tool_message(message)

    def test_render_tool_message_multiline_indentation(self):
        """Test that multiline tool messages are properly indented."""
        message = ToolMessage(content="Line 1\nLine 2\nLine 3", tool_call_id="1")
        # All lines after first should be indented
        Renderer.render_tool_message(message)

    def test_render_tool_message_empty_content_skips_rendering(self):
        """Test that empty content tool messages are not rendered."""
        message = ToolMessage(content="", tool_call_id="1")
        # Should return early without rendering
        Renderer.render_tool_message(message)

    def test_render_tool_message_whitespace_only_skips_rendering(self):
        """Test that whitespace-only content tool messages are not rendered."""
        message = ToolMessage(content="   \n  \t  ", tool_call_id="1")
        # Should return early without rendering
        Renderer.render_tool_message(message)

    def test_render_tool_message_empty_short_content_falls_back(self):
        """Test that empty short_content falls back to text content."""
        message = ToolMessage(content="Actual content", tool_call_id="1")
        message.short_content = ""  # type: ignore[attr-defined]
        # Should fall back to content and render
        Renderer.render_tool_message(message)


class TestRendererUserMessage:
    """Tests for user message rendering."""

    def test_render_user_message_uses_short_content(self):
        """Test that short_content is preferred over full text."""
        message = HumanMessage(content="Very long message " * 100)
        message.short_content = "Short version"  # type: ignore[attr-defined]
        # Should use short_content
        Renderer.render_user_message(message)

    def test_render_user_message_falls_back_to_text(self):
        """Test that message text is used when short_content unavailable."""
        message = HumanMessage(content="Regular message")
        # Should use regular content
        Renderer.render_user_message(message)


class TestRendererHTMLWrapping:
    """Tests for HTML wrapping in code blocks to preserve formatting."""

    def test_pure_html_block_wrapped(self):
        """Test that a pure HTML block gets wrapped in code fences."""
        content = """<table border="1">
  <tr>
    <th>Header 1</th>
    <th>Header 2</th>
  </tr>
</table>"""
        result = wrap_html_in_code_blocks(content)
        assert result.startswith("```html\n")
        assert result.endswith("\n```")
        assert "<table" in result
        assert "  <tr>" in result

    def test_html_already_in_code_block_not_wrapped(self):
        """Test that HTML already in code blocks is not wrapped again."""
        content = """```html
<div>Already in code block</div>
```"""
        result = wrap_html_in_code_blocks(content)
        assert result.count("```html") == 1
        assert result.count("```") == 2

    def test_html_mixed_with_markdown_text(self):
        """Test HTML blocks separated from markdown prose."""
        content = """Here is some markdown text.

<table>
  <tr><td>Cell</td></tr>
</table>

And here is more markdown text."""
        result = wrap_html_in_code_blocks(content)
        assert "Here is some markdown text." in result
        assert "And here is more markdown text." in result
        assert "```html" in result
        assert result.count("```") == 2

    def test_inline_html_in_prose(self):
        """Test inline HTML tags in prose get wrapped."""
        content = "This is a paragraph with <strong>bold</strong> text."
        result = wrap_html_in_code_blocks(content)
        assert "```html" in result
        assert "<strong>bold</strong>" in result

    def test_multiple_separate_html_blocks(self):
        """Test multiple HTML blocks are each wrapped separately."""
        content = """<div>Block 1</div>

Some text between.

<span>Block 2</span>"""
        result = wrap_html_in_code_blocks(content)
        assert result.count("```html") == 2
        assert result.count("```") == 4
        assert "Some text between." in result

    def test_xml_tags_treated_as_html(self):
        """Test XML tags are wrapped like HTML."""
        content = """<config>
  <setting>value</setting>
</config>"""
        result = wrap_html_in_code_blocks(content)
        assert "```html" in result
        assert "<config>" in result

    def test_already_escaped_html_not_wrapped(self):
        """Test already escaped HTML is left as-is."""
        content = "&lt;div&gt;Already escaped&lt;/div&gt;"
        result = wrap_html_in_code_blocks(content)
        assert "```html" not in result
        assert result == content

    def test_empty_lines_between_html_tags_included(self):
        """Test that HTML block includes empty lines between tags."""
        content = """<div>

</div>"""
        result = wrap_html_in_code_blocks(content)
        assert "```html" in result

    def test_html_with_code_blocks_and_prose(self):
        """Test complex mixing of code blocks, HTML, and prose."""
        content = """# Title

Some text here.

```python
print("code")
```

<table>
  <tr><td>Data</td></tr>
</table>

More text.

```js
const x = 1;
```

<div>HTML</div>"""
        result = wrap_html_in_code_blocks(content)
        assert "# Title" in result
        assert "Some text here." in result
        assert "```python" in result
        assert "```js" in result
        assert result.count("```html") == 2
        assert "<table>" in result
        assert "<div>HTML</div>" in result

    def test_partial_html_tag_not_wrapped(self):
        """Test malformed/partial HTML without closing > is escaped (not wrapped in code block)."""
        content = "<div incomplete"
        result = wrap_html_in_code_blocks(content)
        assert "```html" not in result
        # Partial tags should be escaped to prevent Rich from stripping them
        assert result == "&lt;div incomplete"

    def test_consecutive_lines_with_html_kept_together(self):
        """Test consecutive HTML lines stay in same code block."""
        content = """<ul>
<li>Item 1</li>
<li>Item 2</li>
</ul>"""
        result = wrap_html_in_code_blocks(content)
        assert result.count("```html") == 1
        assert result.count("```") == 2

    def test_non_html_lines_between_html_split_blocks(self):
        """Test that non-HTML lines split HTML into multiple blocks."""
        content = """<div>Block 1</div>
Regular text
<div>Block 2</div>"""
        result = wrap_html_in_code_blocks(content)
        assert result.count("```html") == 2
        assert "Regular text" in result
        # Verify "Regular text" appears outside HTML code blocks by checking
        # it's not between ```html and ``` markers

        # Remove all HTML code blocks from result
        result_without_html_blocks = re.sub(
            r"```html\n.*?\n```", "", result, flags=re.DOTALL
        )
        # "Regular text" should still be present after removing HTML blocks
        assert "Regular text" in result_without_html_blocks

    def test_code_block_with_different_language(self):
        """Test existing code blocks with languages are preserved."""
        content = """```typescript
const foo: string = "<not html>";
```

<div>Real HTML</div>"""
        result = wrap_html_in_code_blocks(content)
        assert "```typescript" in result
        assert "```html" in result
        assert result.count("```") == 4

    def test_empty_content(self):
        """Test empty content returns empty string."""
        content = ""
        result = wrap_html_in_code_blocks(content)
        assert result == ""

    def test_mixed_raw_html_and_entities_wrapped(self):
        """Test that lines with both raw HTML tags and HTML entities are properly wrapped.

        Regression test for security issue where `<div>&amp;</div>` was
        incorrectly passing through unescaped.
        """
        content = "<div>&amp;</div>"
        result = wrap_html_in_code_blocks(content)
        # Should be wrapped in code block, not pass through unchanged
        assert "```html" in result
        assert "<div>&amp;</div>" in result
        # Verify it's wrapped, not just escaped
        assert result.startswith("```html\n")
        assert result.endswith("\n```")

    def test_only_markdown_no_html(self):
        """Test pure markdown without HTML is unchanged."""
        content = """# Heading

Some **bold** text and *italic* text.

- List item 1
- List item 2"""
        result = wrap_html_in_code_blocks(content)
        assert result == content
        assert "```html" not in result

    def test_html_attribute_containing_greater_than(self):
        """Test HTML with > inside attribute value is correctly wrapped."""
        content = '<div title="test>more">content</div>'
        result = wrap_html_in_code_blocks(content)
        assert "```html" in result
        assert '<div title="test>more">content</div>' in result

    def test_multiple_tags_on_single_line(self):
        """Test multiple complete HTML tags on same line are wrapped."""
        content = "<div>test</div><span>more</span>"
        result = wrap_html_in_code_blocks(content)
        assert "```html" in result
        assert "<div>test</div><span>more</span>" in result

    def test_nested_html_tags(self):
        """Test nested HTML tags are correctly detected and wrapped."""
        content = "<div><span>test</span></div>"
        result = wrap_html_in_code_blocks(content)
        assert "```html" in result
        assert "<div><span>test</span></div>" in result
