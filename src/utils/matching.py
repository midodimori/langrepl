"""Content matching utilities for flexible text comparison."""

import textwrap
from difflib import SequenceMatcher


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace for flexible matching.

    - Converts CRLF to LF
    - Strips trailing whitespace from each line
    - Removes common leading indentation
    """
    normalized = text.replace("\r\n", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    result = "\n".join(lines)
    dedented = textwrap.dedent(result)
    return dedented


def find_fuzzy_match(
    content: str, search: str, threshold: float = 0.85
) -> tuple[str, float, int] | None:
    """Find closest matching content using similarity scoring.

    Args:
        content: The content to search in
        search: The text to search for
        threshold: Minimum similarity ratio (0.0-1.0)

    Returns:
        Tuple of (matched_text, similarity_ratio, line_number) or None
    """
    search_lines = search.split("\n")
    content_lines = content.split("\n")

    best_match: str | None = None
    best_ratio = 0.0
    best_line = -1

    window_size = len(search_lines)
    for i in range(len(content_lines) - window_size + 1):
        window = "\n".join(content_lines[i : i + window_size])
        ratio = SequenceMatcher(None, search, window).ratio()

        if ratio > best_ratio:
            best_ratio = ratio
            best_match = window
            best_line = i + 1

    if best_ratio >= threshold and best_match is not None:
        return best_match, best_ratio, best_line
    return None


def find_progressive_match(content: str, search: str) -> tuple[bool, int, int]:
    """Find content using progressive matching strategies.

    Strategy 1: Exact string match
    Strategy 2: Normalized whitespace match (sliding window)

    Args:
        content: The content to search in
        search: The text to search for

    Returns:
        Tuple of (found, start_index, end_index)
        If not found, returns (False, -1, -1)
    """
    # Strategy 1: Exact match
    if search in content:
        idx = content.find(search)
        return True, idx, idx + len(search)

    # Strategy 2: Normalized whitespace (sliding window)
    normalized_search = normalize_whitespace(search).rstrip("\n")
    search_line_count = normalized_search.count("\n") + 1

    content_lines = content.split("\n")
    for i in range(len(content_lines) - search_line_count + 1):
        window_lines = content_lines[i : i + search_line_count]
        window = "\n".join(window_lines)

        if normalize_whitespace(window).rstrip("\n") == normalized_search:
            start_idx = sum(len(line) + 1 for line in content_lines[:i])
            end_idx = start_idx + len(window)
            return True, start_idx, end_idx

    return False, -1, -1


def format_match_error(
    file_path: str,
    edit_num: int,
    search_content: str,
    file_content: str,
    preview_len: int = 200,
) -> str:
    """Format a helpful error message when content match fails.

    Args:
        file_path: Path to the file
        edit_num: Edit operation number (1-indexed)
        search_content: Content that was being searched for
        file_content: Actual file content
        preview_len: Maximum length of preview text

    Returns:
        Formatted error message
    """
    fuzzy_result = find_fuzzy_match(file_content, search_content)

    if fuzzy_result:
        match_text, ratio, line_num = fuzzy_result
        return (
            f"Old content not found in file: {file_path}\n"
            f"Edit #{edit_num} failed.\n\n"
            f"Closest match (similarity: {ratio:.1%}) near line {line_num}:\n\n"
            f"Expected:\n{search_content[:preview_len]}"
            f"{'...' if len(search_content) > preview_len else ''}\n\n"
            f"Found:\n{match_text[:preview_len]}"
            f"{'...' if len(match_text) > preview_len else ''}\n\n"
            f"Tip: Read the file first to see exact content."
        )
    else:
        return (
            f"Old content not found in file: {file_path}\n"
            f"Edit #{edit_num} failed. No similar content found.\n\n"
            f"Searching for:\n{search_content[:preview_len]}"
            f"{'...' if len(search_content) > preview_len else ''}\n\n"
            f"Tip: Read the file first to see exact content."
        )
