import difflib
import json
import re
import shutil
import uuid
from typing import Any, TypeAlias

from langchain_core.messages import AIMessage, ToolMessage
from rich.markup import escape

from src.cli.theme import theme

TemplateData: TypeAlias = dict[str, "TemplateData"] | list["TemplateData"] | str | Any


def render_templates(
    data: TemplateData, context: dict[str, Any] | None
) -> TemplateData:
    """Render templates with the given context."""
    context = context or {}
    if isinstance(data, dict):
        return {key: render_templates(value, context) for key, value in data.items()}
    elif isinstance(data, list):
        return [render_templates(item, context) for item in data]
    elif isinstance(data, str):
        try:
            return data.format(**context)
        except (KeyError, ValueError):
            return data
    else:
        return data


def format_tool_response(data: Any) -> tuple[str, str | None]:
    """Recursively format tool response content for display.

    Args:
        data: Tool response data (can be parsed JSON or string)

    Returns:
        Tuple of (content, short_content). short_content is None if not available.
    """
    if isinstance(data, ToolMessage):
        # Extract both content and short_content from ToolMessage
        content = data.text
        short_content = getattr(data, "short_content", None)
        return content, short_content

    if isinstance(data, str):
        data = data.strip()
        if data.startswith(("{", "[")):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return data, None
        else:
            return data, None

    if isinstance(data, (list, tuple)):
        formatted_items = []
        for item in data:
            if item is None:
                continue
            formatted, _ = format_tool_response(item)
            if formatted:
                formatted_items.append(formatted)
        return "\n".join(formatted_items), None

    elif isinstance(data, dict):
        formatted_dict = {
            key: format_tool_response(value)[0] for key, value in data.items()
        }
        return json.dumps(formatted_dict, indent=2, ensure_ascii=False), None

    elif data is None:
        return "", None

    else:
        return str(data), None


def truncate_text(text: str, max_length: int) -> str:
    """Truncate text to a maximum length with ellipsis if needed.

    Args:
        text: Input text
        max_length: Maximum length

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[:max_length] + "..."


def create_tool_message(
    result: Any,
    tool_name: str,
    tool_call_id: str,
    is_error: bool | None = None,
    return_direct: bool | None = None,
) -> ToolMessage:
    """Create a ToolMessage from a tool execution result with proper formatting.

    Handles content extraction, short_content generation, and metadata extraction.

    Args:
        result: Tool result (can be string, AIMessage, ToolMessage, or any object)
        tool_name: Name of the tool
        tool_call_id: ID of the tool call
        is_error: Override is_error flag (if None, extracted from result via getattr)
        return_direct: Override return_direct flag (if None, extracted from result via getattr)

    Returns:
        Properly formatted ToolMessage with content and short_content
    """
    # Extract metadata from result if not explicitly provided
    final_is_error = (
        is_error if is_error is not None else getattr(result, "is_error", False)
    )
    final_return_direct = (
        return_direct
        if return_direct is not None
        else getattr(result, "return_direct", False)
    )

    # Handle AIMessage specially, let format_tool_response handle everything else
    if isinstance(result, AIMessage):
        content = str(result.text)
        short_content = None
    else:
        content, short_content = format_tool_response(result)

    # Generate short_content if not available
    if short_content is None:
        # For errors, use full content; otherwise truncate
        short_content = content if final_is_error else truncate_text(content, 200)

    return ToolMessage(
        id=str(uuid.uuid4()),
        name=tool_name,
        content=content,
        tool_call_id=tool_call_id,
        short_content=short_content,
        is_error=final_is_error,
        return_direct=final_return_direct,
    )


def generate_diff(
    old_content: str,
    new_content: str,
    context_lines: int = 3,
    full_content: str | None = None,
) -> list[str]:
    """Generate unified diff lines between old and new content.

    Args:
        old_content: Original content
        new_content: New content
        context_lines: Number of context lines to show
        full_content: Full file content to calculate accurate line numbers

    Returns:
        List of diff lines (including headers)
    """
    old_lines = old_content.splitlines()
    new_lines = new_content.splitlines()

    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            lineterm="",
            n=context_lines,
        )
    )

    # If full_content provided, adjust line numbers in hunk headers
    if full_content and old_content:
        # Find the starting line number of old_content in full_content
        full_lines = full_content.splitlines()
        start_line = _find_content_line_number(full_lines, old_lines)

        if start_line > 0:
            # Adjust hunk headers to show correct line numbers
            diff_lines = _adjust_diff_line_numbers(diff_lines, start_line)

    return diff_lines


def _find_content_line_number(full_lines: list[str], content_lines: list[str]) -> int:
    """Find the starting line number (1-based) where content appears in full file.

    Args:
        full_lines: All lines from the full file
        content_lines: Lines to search for

    Returns:
        1-based line number where content starts, or 0 if not found
    """
    if not content_lines:
        return 0

    content_len = len(content_lines)
    for i in range(len(full_lines) - content_len + 1):
        if full_lines[i : i + content_len] == content_lines:
            return i + 1  # Return 1-based line number

    return 0


def _adjust_diff_line_numbers(diff_lines: list[str], start_line: int) -> list[str]:
    """Adjust line numbers in diff hunk headers.

    Args:
        diff_lines: Original diff lines
        start_line: 1-based starting line number in the full file

    Returns:
        Diff lines with adjusted hunk headers
    """
    adjusted = []
    line_offset = start_line - 1  # Convert to 0-based offset

    for line in diff_lines:
        if line.startswith("@@"):
            # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
            match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)", line)
            if match:
                old_start = int(match.group(1)) + line_offset
                old_count = match.group(2) or "1"
                new_start = int(match.group(3)) + line_offset
                new_count = match.group(4) or "1"
                suffix = match.group(5)

                adjusted_line = (
                    f"@@ -{old_start},{old_count} +{new_start},{new_count} @@{suffix}"
                )
                adjusted.append(adjusted_line)
            else:
                adjusted.append(line)
        else:
            adjusted.append(line)

    return adjusted


def _wrap_diff_line(
    code: str,
    marker: str,
    color: str,
    line_num: int | None,
    width: int,
    term_width: int,
) -> list[str]:
    """Wrap long diff lines with proper indentation.

    Args:
        code: Code content to wrap
        marker: Diff marker ('+', '-', ' ')
        color: Rich color for the line
        line_num: Line number to display (None for continuation lines)
        width: Width for line number column
        term_width: Terminal width

    Returns:
        List of formatted lines (may be multiple if wrapped)
    """
    # Escape Rich markup in code content
    code = escape(code)

    prefix_len = width + 4  # line_num + space + marker + 2 spaces
    available_width = term_width - prefix_len

    if len(code) <= available_width:
        if line_num is not None:
            return [f"[{color}]{line_num:>{width}} {marker}  {code}[/{color}]"]
        return [f"[{color}]{' ' * width} {marker}  {code}[/{color}]"]

    lines = []
    remaining = code
    first = True

    while remaining:
        chunk = remaining[:available_width]
        remaining = remaining[available_width:]

        if first and line_num is not None:
            lines.append(f"[{color}]{line_num:>{width}} {marker}  {chunk}[/{color}]")
            first = False
        else:
            lines.append(f"[{color}]{' ' * width} {marker}  {chunk}[/{color}]")

    return lines


def format_diff_rich(diff_lines: list[str]) -> str:
    """Format diff lines with Rich markup in inline format with line numbers.

    Args:
        diff_lines: Diff lines from generate_diff()

    Returns:
        Rich-formatted inline diff string with line numbers
    """
    if not diff_lines:
        return "[muted]No changes detected[/muted]"

    # Get terminal width
    term_width = shutil.get_terminal_size().columns

    # Find max line number for width calculation
    max_line = max(
        (
            int(m.group(i))
            for line in diff_lines
            if (m := re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)", line))
            for i in (1, 2)
        ),
        default=0,
    )
    width = max(3, len(str(max_line)))

    formatted_lines = []
    old_num = new_num = 0

    for line in diff_lines:
        if line.strip() == "...":
            formatted_lines.append(
                f"[{theme.context_color}]...[/{theme.context_color}]"
            )
        elif line.startswith(("---", "+++")):
            continue
        elif m := re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)", line):
            old_num, new_num = int(m.group(1)), int(m.group(2))
        elif line.startswith("-"):
            formatted_lines.extend(
                _wrap_diff_line(
                    line[1:], "-", theme.deletion_color, old_num, width, term_width
                )
            )
            old_num += 1
        elif line.startswith("+"):
            formatted_lines.extend(
                _wrap_diff_line(
                    line[1:], "+", theme.addition_color, new_num, width, term_width
                )
            )
            new_num += 1
        elif line.startswith(" "):
            formatted_lines.extend(
                _wrap_diff_line(
                    line[1:], " ", theme.context_color, old_num, width, term_width
                )
            )
            old_num += 1
            new_num += 1

    return "\n".join(formatted_lines)
