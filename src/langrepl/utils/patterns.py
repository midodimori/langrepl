"""Pattern matching utilities with negative pattern support."""

from collections.abc import Callable
from fnmatch import fnmatch


def matches_patterns(
    patterns: list[str],
    matcher: Callable[[str], bool],
) -> bool:
    """Match against patterns with negative (!pattern) support.

    Returns True if matches ≥1 positive AND matches 0 negatives.
    Returns False if no positive patterns exist.
    """
    positives = [p for p in patterns if not p.startswith("!")]
    negatives = [p[1:] for p in patterns if p.startswith("!")]

    if not positives:
        return False

    return any(matcher(p) for p in positives) and not any(matcher(p) for p in negatives)


def two_part_matcher(
    name: str, module: str, on_invalid: Callable[[str], None] | None = None
) -> Callable[[str], bool]:
    """Matcher for 2-part patterns (module:name)."""

    def match(p: str) -> bool:
        parts = p.split(":")
        if len(parts) != 2:
            if on_invalid:
                on_invalid(p)
            return False
        mod_p, name_p = parts
        return fnmatch(module, mod_p) and fnmatch(name, name_p)

    return match


def three_part_matcher(
    name: str,
    module: str,
    category: str,
    on_invalid: Callable[[str], None] | None = None,
) -> Callable[[str], bool]:
    """Matcher for 3-part patterns (category:module:name)."""

    def match(p: str) -> bool:
        parts = p.split(":")
        if len(parts) != 3:
            if on_invalid:
                on_invalid(p)
            return False
        cat_p, mod_p, name_p = parts
        return (
            fnmatch(category, cat_p)
            and fnmatch(module, mod_p)
            and fnmatch(name, name_p)
        )

    return match


def mcp_server_matcher(
    server_name: str, category: str, on_invalid: Callable[[str], None] | None = None
) -> Callable[[str], bool]:
    """Matcher for MCP patterns (mcp:server:*). Tool part must be '*'."""

    def match(p: str) -> bool:
        parts = p.split(":")
        if len(parts) != 3:
            return False
        cat_p, server_p, tool_p = parts
        if cat_p != category:
            return False
        if tool_p != "*":
            if on_invalid:
                on_invalid(p)
            return False
        return fnmatch(server_name, server_p)

    return match
