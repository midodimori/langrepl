"""Rich-based UI rendering and message formatting."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

import mdformat
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from rich.cells import cell_len
from rich.console import Console, ConsoleOptions, Group, NewLine, RenderableType
from rich.markdown import CodeBlock, Markdown
from rich.panel import Panel
from rich.segment import Segment
from rich.style import Style
from rich.syntax import Syntax, SyntaxTheme
from rich.table import Table
from rich.text import Text

from src.cli.core.context import Context
from src.cli.theme import console
from src.cli.ui.markdown import wrap_html_in_code_blocks
from src.core.constants import UNKNOWN
from src.core.settings import settings
from src.utils.version import get_latest_features

if TYPE_CHECKING:
    from langchain_core.runnables.graph import Graph


def _fix_escaped_code_fences(content: str) -> str:
    """Fix escaped code fence delimiters that should be proper markdown.

    Some LLMs escape closing backticks (``` -> \\`\\`\\`) which prevents
    proper code block rendering. This must run before mdformat.
    """
    content = re.sub(
        r"```\n(.*?)\n\\`\\`\\`", r"```\n\1\n```", content, flags=re.DOTALL
    )
    content = re.sub(
        r"```([^\n]*)\n(.*?)\n\\`\\`\\`",
        r"```\1\n\2\n```",
        content,
        flags=re.DOTALL,
    )
    content = re.sub(
        r"\\`\\`\\`([^\n]*)\n(.*?)\n\\`\\`\\`",
        r"```\1\n\2\n```",
        content,
        flags=re.DOTALL,
    )
    return content


class TransparentSyntax(Syntax):
    """Syntax highlighter with transparent background."""

    @classmethod
    def get_theme(cls, name):
        """Wrap theme to strip background colors from all token styles."""
        base_theme = super().get_theme(name)

        class TransparentThemeWrapper(SyntaxTheme):
            def __init__(self, base):
                self.base = base

            def get_style_for_token(self, token_type):
                style = self.base.get_style_for_token(token_type)
                return Style(
                    color=style.color,
                    bold=style.bold,
                    italic=style.italic,
                    underline=style.underline,
                )

            def get_background_style(self):
                return Style()

        return TransparentThemeWrapper(base_theme)


class TransparentCodeBlock(CodeBlock):
    """Code block with transparent background."""

    def __rich_console__(self, console: Console, options: ConsoleOptions):
        yield TransparentSyntax(
            str(self.text).rstrip(), self.lexer_name, theme=self.theme
        )


class TransparentMarkdown(Markdown):
    """Markdown with transparent code blocks."""

    elements = {
        **Markdown.elements,
        "code_block": TransparentCodeBlock,
        "fence": TransparentCodeBlock,
    }


class PrefixedMarkdown:
    """Markdown with a styled prefix on the first line."""

    def __init__(
        self,
        prefix: str,
        content: str,
        prefix_style: str = "success",
        code_theme: str = "dracula",
    ):
        self.prefix = prefix
        self.prefix_style = prefix_style
        self.content = content
        self.code_theme = code_theme

    def __rich_console__(self, console: Console, options: ConsoleOptions):
        """Render markdown with prefix on first line and indent all subsequent lines."""
        # Calculate indentation width using visual cell width
        indent_width = cell_len(self.prefix)

        # Adjust rendering width to account for prefix/indent
        adjusted_options = options.update_width(options.max_width - indent_width)

        # Render all content as markdown with adjusted width
        markdown = TransparentMarkdown(self.content, code_theme=self.code_theme)
        segments = list(console.render(markdown, adjusted_options))

        if not segments:
            return

        # Get prefix style from console theme
        prefix_style = console.get_style(self.prefix_style)
        prefix_segment = Segment(self.prefix, prefix_style)

        # Create indentation segment
        indent = " " * indent_width
        indent_segment = Segment(indent)

        # Track whether we've added the prefix yet
        prefix_added = False
        at_line_start = True

        for segment in segments:
            # Skip completely empty segments
            if not segment.text:
                continue

            # Split segment by newlines to handle indentation per line
            lines = segment.text.split("\n")

            for i, line in enumerate(lines):
                # Add prefix to first line content
                if not prefix_added and line:
                    yield prefix_segment
                    prefix_added = True
                    at_line_start = False
                # Add indentation to subsequent lines
                elif at_line_start and line:
                    yield indent_segment
                    at_line_start = False

                # Yield the line content
                if line or i < len(lines) - 1:  # Include empty lines except trailing
                    yield Segment(line, segment.style)

                # Handle newlines between lines
                if i < len(lines) - 1:
                    yield Segment("\n")
                    at_line_start = True

        # Handle case where no content was found
        if not prefix_added:
            yield prefix_segment


class Renderer:
    """Handles rendering of UI elements using Rich."""

    @staticmethod
    def show_welcome(context: Context) -> None:
        """Display ASCII logo with features in a responsive table."""
        logo = r"""
 |▔|__ _ _ _  __ _ _ _ ___ _ __|▔|
 | / _` | ' \/ _` | '_/ -_) '_ \ |
 |_\__,_|_||_\__, |_| \___| .__/_|
             |___/        |_|
"""
        features = get_latest_features()

        # Build the features' list with header
        features_lines = ["What's New:"]
        for feature in features:
            features_lines.append(f"• {feature}")

        # Create responsive table
        table = Table.grid(padding=(0, 2), expand=False)
        table.add_column(style="accent", no_wrap=True)
        table.add_column(ratio=1)

        table.add_row(
            Text(logo.strip("\n"), style="accent"),
            Text("\n".join(features_lines), style="muted"),
        )

        console.print(table)
        console.print("")

    @staticmethod
    def render_user_message(message: HumanMessage) -> None:
        """Render user message."""
        content = getattr(message, "short_content", None) or message.text

        # Calculate the visual width of the prompt prefix
        prompt_prefix = settings.cli.prompt_style
        prefix_width = cell_len(prompt_prefix)
        indent = " " * prefix_width

        # Split content into lines and add indentation
        lines = content.split("\n")
        formatted_lines = []
        for i, line in enumerate(lines):
            if i == 0:
                formatted_lines.append(f"[prompt]{prompt_prefix}[/prompt]{line}")
            else:
                formatted_lines.append(f"{indent}{line}")

        console.print("\n".join(formatted_lines))
        console.print("")

    @staticmethod
    def _extract_thinking_from_metadata(message: AIMessage) -> str | None:
        """Extract thinking from message metadata (e.g., Bedrock stores it here)."""
        if not hasattr(message, "additional_kwargs"):
            return None
        if not isinstance(message.additional_kwargs, dict):
            return None
        thinking_data = message.additional_kwargs.get("thinking")
        if isinstance(thinking_data, dict):
            return thinking_data.get("text")
        return None

    @staticmethod
    def _extract_thinking_and_text_from_blocks(
        blocks: list[str | dict],
    ) -> tuple[list[str], list[str]]:
        """Extract text and thinking blocks separately.

        Returns:
            Tuple of (text_parts, thinking_parts)
        """
        texts = []
        thinking_blocks = []

        for block in blocks:
            if isinstance(block, str):
                text = block.strip(" ")
                if text and text[-1] != "\n":
                    text += "\n"
                texts.append(text)
            elif isinstance(block, dict):
                block_type = block.get("type", "")
                if block_type == "text":
                    text = block.get("text", "").strip(" ")
                    if text:
                        if text[-1] != "\n":
                            text += "\n"
                        texts.append(text)
                elif block_type == "thinking":
                    thinking_blocks.append(block.get("thinking", ""))
                elif block_type == "reasoning":
                    summary = block.get("summary", [])
                    if isinstance(summary, list):
                        summary_texts = [
                            s.get("text", "") for s in summary if isinstance(s, dict)
                        ]
                        if summary_texts:
                            thinking_blocks.append("\n".join(summary_texts))
                elif block_type == "reasoning_content":
                    reasoning_text = block.get("reasoning_content", "")
                    if reasoning_text:
                        thinking_blocks.append(reasoning_text)

        return texts, thinking_blocks

    @staticmethod
    def _format_tool_call(tool_call: dict[str, Any]) -> Text:
        """Format a single tool call with improved readability."""
        tool_name = tool_call.get("name", UNKNOWN)
        tool_args = cast(dict[str, Any], tool_call.get("args", {}))

        # Build the text with formatting
        result = Text()
        result.append("⚙ ", style="indicator")
        result.append(tool_name, style="bold")
        result.append("\n")

        if tool_args:
            for k, v in tool_args.items():
                # Format value with truncation if needed
                value_str = str(v)
                if len(value_str) > 200:
                    value_str = value_str[:200] + "..."

                result.append(f"  {k} : ")
                result.append(value_str)
                result.append("\n")

        return result

    @staticmethod
    def render_assistant_message(message: AIMessage) -> None:
        """Render an assistant message with optional tool calls."""
        if not message.content and not message.tool_calls:
            return

        content: str | list[str | dict] = message.content
        tool_calls = [dict(tc) for tc in message.tool_calls]
        is_error = getattr(message, "is_error", False)

        if not content:
            # Only tool calls, no content
            if tool_calls:
                for i, tool_call in enumerate(tool_calls):
                    console.print(Renderer._format_tool_call(tool_call))
                    if i < len(tool_calls) - 1:
                        console.print("")
            return

        if is_error:
            console.print(Text(cast(str, content), style="error"))
            return

        # Extract thinking from all sources
        thinking_parts = []

        # 1. Check metadata first (Bedrock, etc.)
        metadata_thinking = Renderer._extract_thinking_from_metadata(message)
        if metadata_thinking:
            thinking_parts.append(metadata_thinking)

        # 2. Extract from content blocks
        if isinstance(content, list):
            text_parts, block_thinking = (
                Renderer._extract_thinking_and_text_from_blocks(content)
            )
            thinking_parts.extend(block_thinking)
            content = "".join(text_parts)

        # 3. Extract XML-style thinking tags
        if isinstance(content, str):
            content, xml_thinking = Renderer._extract_thinking_tags(content)
            if xml_thinking:
                thinking_parts.append(xml_thinking)

        # Render thinking first if present
        parts: list[RenderableType] = []
        if thinking_parts:
            parts.append(Text("\n\n".join(thinking_parts), style="italic dim"))
            parts.append(NewLine())

        # Render main content
        if isinstance(content, str):
            content = _fix_escaped_code_fences(content)
            try:
                content = mdformat.text(content)
            except Exception:
                pass

            content = wrap_html_in_code_blocks(content)
        if content:
            parts.append(
                PrefixedMarkdown(
                    "◆︎ ", content, prefix_style="indicator", code_theme="dracula"
                )
            )

        # Print content if any
        if parts:
            console.print(Group(*parts))

        # Print tool calls with separator if we had content
        if tool_calls:
            if parts:
                console.print(NewLine())
            for tool_call in tool_calls:
                console.print(Renderer._format_tool_call(tool_call))
        elif parts:
            console.print("")

    @staticmethod
    def render_tool_message(message: ToolMessage) -> None:
        """Render a tool execution message with Rich markup support."""
        content = getattr(message, "short_content", None) or message.text

        # Skip rendering if content is empty or None
        if not content or (isinstance(content, str) and not content.strip()):
            return

        is_error = (
            getattr(message, "is_error", False)
            or getattr(message, "status", None) == "error"
        )

        formatted_lines = []
        for i, line in enumerate(content.split("\n")):
            if i == 0:
                formatted_lines.append(f"  ㄴ{line}")
            else:
                formatted_lines.append(f"    {line}")

        formatted_content = "\n".join(formatted_lines)

        if is_error:
            console.print(Text(formatted_content, style="error"))
        else:
            console.print(formatted_content)

        console.print("")

    @staticmethod
    def render_help(commands_dict: dict[str, Any]) -> None:
        """Render help information dynamically from registered commands."""
        content_parts = []

        # Commands section
        commands_table = Table.grid(padding=(0, 2))
        commands_table.add_column(style="command", justify="left", width=20)
        commands_table.add_column(style="secondary")

        # Dynamic generation from registered commands
        for command_name, command_func in commands_dict.items():
            # Extract description from docstring
            description = "No description available"
            if command_func.__doc__:
                description = command_func.__doc__.strip()

            commands_table.add_row(command_name, description)

        content_parts.append(commands_table)

        help_panel = Panel(
            Group(*content_parts),
            title="[accent]Help[/accent]",
            border_style="border",
            padding=(1, 2),
        )

        console.print(help_panel)
        console.print("")

    @staticmethod
    def render_hotkeys(hotkeys: dict[str, str]) -> None:
        """Render keyboard shortcuts."""
        hotkeys_table = Table.grid(padding=(0, 2))
        hotkeys_table.add_column(style="command", justify="left", width=20)
        hotkeys_table.add_column(style="secondary")

        for shortcut, description in hotkeys.items():
            hotkeys_table.add_row(shortcut, description)

        hotkeys_panel = Panel(
            Group(hotkeys_table),
            title="[accent]Keyboard Shortcuts[/accent]",
            border_style="border",
            padding=(1, 2),
        )

        console.print(hotkeys_panel)
        console.print("")

    @staticmethod
    def _extract_thinking_tags(content: str) -> tuple[str, str | None]:
        """Extract thinking content from XML-style tags like <think>...</think>.

        Only extracts if <think> appears at the start of content (provider pattern).
        If <think> tags appear mid-content, they're treated as literal text.

        Args:
            content: The content that may contain thinking tags

        Returns:
            Tuple of (cleaned_content, thinking_content)
        """
        content_stripped = content.lstrip()

        # Only extract if content starts with <think> tag (provider-generated pattern)
        if not content_stripped.startswith("<think>"):
            return content, None

        think_pattern = r"<think>(.*?)</think>"
        matches = re.findall(think_pattern, content, re.DOTALL)

        if matches:
            thinking_content = "\n\n".join(match.strip() for match in matches)
            cleaned_content = re.sub(
                think_pattern, "", content, flags=re.DOTALL
            ).strip()
            return cleaned_content, thinking_content

        return content, None

    @staticmethod
    def render_graph(drawable_graph: Graph) -> None:
        """Render LangGraph visualization as Mermaid diagram.

        Args:
            drawable_graph: The drawable graph from graph.get_graph()
        """
        try:
            mermaid_code = drawable_graph.draw_mermaid()
            console.print("[muted]" + "─" * console.width + "[/muted]", markup=True)

            # Use TransparentSyntax to match markdown code rendering style
            syntax = TransparentSyntax(
                mermaid_code,
                "text",
                theme="dracula",
                line_numbers=False,
                word_wrap=True,
            )
            console.console.print(syntax)

            console.print("[muted]" + "─" * console.width + "[/muted]", markup=True)
            console.print(
                "Copy and visualize at [accent.secondary underline]https://mermaid.live[/accent.secondary underline]",
                markup=True,
            )
            console.print()

        except Exception as e:
            console.print_error(f"Could not generate Mermaid diagram: {e}")
            console.print("")

    @staticmethod
    def render_message(message: AnyMessage) -> None:
        """Render any message."""
        if isinstance(message, HumanMessage):
            Renderer.render_user_message(message)

        elif isinstance(message, AIMessage):
            Renderer.render_assistant_message(message)

        elif isinstance(message, ToolMessage):
            Renderer.render_tool_message(message)
