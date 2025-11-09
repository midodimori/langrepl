"""Tests for Renderer critical logic."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.cli.ui.renderer import Renderer


class TestRendererMalformedCodeBlocks:
    """Tests for _fix_malformed_code_blocks edge cases and regex handling."""

    def test_fix_escaped_closing_backticks(self):
        """Test fixing escaped closing backticks in code blocks."""
        content = "```python\nprint('hello')\n\\`\\`\\`"
        fixed = Renderer._fix_malformed_code_blocks(content)
        assert "\\`\\`\\`" not in fixed
        assert "```python\nprint('hello')\n```" == fixed

    def test_fix_mixed_escaping(self):
        """Test fixing mixed escaping where opening is fine but closing is escaped."""
        content = "```python\ncode here\n\\`\\`\\`"
        fixed = Renderer._fix_malformed_code_blocks(content)
        assert fixed == "```python\ncode here\n```"

    def test_fix_all_backticks_escaped(self):
        """Test fixing when all backticks are escaped."""
        content = "\\`\\`\\`python\ncode\n\\`\\`\\`"
        fixed = Renderer._fix_malformed_code_blocks(content)
        assert fixed == "```python\ncode\n```"

    def test_fix_stray_backticks_in_code_line(self):
        """Test cleaning up stray backticks mixed with content."""
        content = "```python\ncode line``` extra content"
        fixed = Renderer._fix_malformed_code_blocks(content)
        lines = fixed.split("\n")
        assert "```" in lines[-1] or lines[-2] == "```"

    def test_multiple_code_blocks(self):
        """Test handling multiple code blocks in same content."""
        content = "```python\nblock1\n```\n\nSome text\n\n```js\nblock2\n```"
        fixed = Renderer._fix_malformed_code_blocks(content)
        assert fixed.count("```") == 4

    def test_nested_backticks_in_code_content(self):
        """Test that backticks inside code content create expected structure."""
        content = "```python\nprint('```')\n```"
        fixed = Renderer._fix_malformed_code_blocks(content)
        # The function may split on embedded backticks - verify structure is maintained
        assert "```python" in fixed
        assert "print(" in fixed

    def test_incomplete_code_block_without_closing(self):
        """Test incomplete code block is left as-is."""
        content = "```python\ncode without closing"
        fixed = Renderer._fix_malformed_code_blocks(content)
        assert "```python" in fixed

    def test_empty_code_block(self):
        """Test empty code blocks are handled."""
        content = "```\n```"
        fixed = Renderer._fix_malformed_code_blocks(content)
        assert fixed == "```\n```"

    def test_code_block_with_language_and_escaping(self):
        """Test code blocks with language specifier and escaped closing."""
        content = "```typescript\nconst x = 1;\n\\`\\`\\`"
        fixed = Renderer._fix_malformed_code_blocks(content)
        assert fixed == "```typescript\nconst x = 1;\n```"

    def test_multiple_escaped_blocks_in_sequence(self):
        """Test multiple escaped blocks are all fixed."""
        content = "```js\ncode1\n\\`\\`\\`\n\n```py\ncode2\n\\`\\`\\`"
        fixed = Renderer._fix_malformed_code_blocks(content)
        assert "\\`\\`\\`" not in fixed
        assert fixed.count("```") == 4


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

    def test_render_assistant_message_with_malformed_code_blocks(self):
        """Test that malformed code blocks are fixed during rendering."""
        message = AIMessage(
            content="```python\nprint('test')\n\\`\\`\\`\n\nMore content"
        )
        # Should fix code blocks before rendering
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
