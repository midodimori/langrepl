"""Markdown processing utilities using markdown-it for parsing and normalization.

This module provides markdown-it-based utilities for:
- Wrapping HTML in code blocks to preserve it during rendering
- Parsing and analyzing markdown structure
"""

from __future__ import annotations

import html
import re

from markdown_it import MarkdownIt


def _add_fenced_line(
    output: list[str],
    line: str,
    line_idx: int,
    fenced_indices: set[int],
    total_lines: int,
) -> None:
    if line_idx == 0 or line_idx - 1 not in fenced_indices:
        output.append("```html")
    output.append(line)
    if line_idx + 1 >= total_lines or line_idx + 1 not in fenced_indices:
        output.append("```")


def wrap_html_in_code_blocks(content: str) -> str:
    """Wrap HTML in code blocks to prevent Rich from stripping it during rendering.

    This function uses markdown-it token parsing to accurately identify:
    - Code blocks (fenced and indented) - preserved as-is
    - HTML blocks - wrapped in ```html code fences
    - Inline HTML - wrapped in ```html code fences
    - Incomplete HTML - escaped using html.escape()

    Args:
        content: Markdown content with potentially unescaped HTML

    Returns:
        Content with HTML wrapped in ```html code fences and incomplete HTML escaped
    """
    md = MarkdownIt("commonmark")
    tokens = md.parse(content)
    lines = content.split("\n")

    code_block_lines: set[int] = set()
    html_block_lines: set[int] = set()
    lines_with_inline_html: set[int] = set()
    lines_to_escape: set[int] = set()

    for token in tokens:
        # Code blocks: preserve as-is
        if token.type in ("fence", "code_block") and token.map:
            start, end = token.map
            code_block_lines.update(range(start, end))

        # HTML blocks: wrap in code fence (with validation)
        elif token.type == "html_block" and token.map:
            # Validate HTML block content
            block_content = token.content

            # Skip if incomplete tags (no closing >)
            if "<" in block_content and not re.search(r"<[^>]+>", block_content):
                # Has < but no complete tags - mark for escaping
                start, end = token.map
                lines_to_escape.update(range(start, end))
                continue

            # Check if block contains non-HTML lines that should split it
            block_lines = block_content.split("\n")
            has_non_html = False
            for line in block_lines:
                stripped = line.strip()
                if stripped and "<" not in stripped:
                    # Line has no HTML tags
                    has_non_html = True
                    break

            if has_non_html:
                start, end = token.map
                for line_idx in range(start, end):
                    if line_idx < len(lines):
                        line = lines[line_idx]
                        if re.search(r"<[^>]+>", line):
                            html_block_lines.add(line_idx)
            else:
                # Pure HTML block - wrap it
                start, end = token.map
                html_block_lines.update(range(start, end))

        elif token.type == "inline" and token.children and token.map:
            has_html = any(child.type == "html_inline" for child in token.children)
            if has_html:
                start, end = token.map
                for line_idx in range(start, end):
                    if line_idx < len(lines) and re.search(r"<[^>]+>", lines[line_idx]):
                        lines_with_inline_html.add(line_idx)

    output = []

    for i, line in enumerate(lines):
        # Lines to escape (incomplete HTML): escape
        if i in lines_to_escape:
            output.append(html.escape(line))

        # Lines in code blocks: preserve as-is
        elif i in code_block_lines:
            output.append(line)

        elif i in html_block_lines:
            _add_fenced_line(output, line, i, html_block_lines, len(lines))

        elif i in lines_with_inline_html:
            _add_fenced_line(output, line, i, lines_with_inline_html, len(lines))

        # Regular lines: preserve
        else:
            output.append(line)

    return "\n".join(output)
