"""Path utilities."""

import glob
import re
from pathlib import Path

from pathspec.patterns.gitwildmatch import GitWildMatchPattern


class SymlinkEscapeError(ValueError):
    """Raised when a symlink resolves outside allowed boundaries."""


def resolve_path(working_dir: str, path: str) -> Path:
    """Resolve a path relative to working directory if not absolute.

    Special cases:
        - '/' is treated as the working directory itself
        - '~' is expanded to user's home directory
    """
    working_path = Path(working_dir).resolve()

    if path == "/":
        return working_path

    expanded_path = Path(path).expanduser()

    if expanded_path.is_absolute():
        resolved = expanded_path.resolve()
    else:
        resolved = (working_path / path).resolve()

    if not expanded_path.is_absolute():
        original = working_path / path
        if original.exists() and is_symlink_escape(original, [working_path]):
            raise SymlinkEscapeError(
                f"Symlink escapes working directory: {path} -> {resolved}"
            )

    return resolved


def is_path_within(path: Path, boundaries: list[Path]) -> bool:
    """Check if path is within any of the boundary directories."""
    resolved = path.resolve() if path.exists() else path
    return any(resolved == b or resolved.is_relative_to(b) for b in boundaries)


def is_symlink_escape(path: Path, allowed_boundaries: list[Path]) -> bool:
    """Check if a symlink resolves outside allowed boundaries."""
    if not path.is_symlink():
        return False

    try:
        resolved = path.resolve()
    except (OSError, RuntimeError):
        return True

    return not is_path_within(resolved, allowed_boundaries)


def expand_pattern(
    pattern: str, working_dir: Path, include_nonexistent: bool = False
) -> list[Path]:
    """Expand a glob pattern to matching paths.

    Args:
        pattern: Path pattern, may include ~ and glob wildcards
        working_dir: Base directory for relative patterns
        include_nonexistent: If True, include non-existent literal paths
    """
    expanded = Path(pattern).expanduser()
    base_path = expanded if expanded.is_absolute() else working_dir / expanded

    pattern_str = str(base_path)
    if glob.has_magic(pattern_str):
        parts = base_path.parts
        glob_base = Path(parts[0])  # anchor (e.g., "/" or "C:\")

        for i, part in enumerate(parts[1:], start=1):
            if glob.has_magic(part):
                if glob_base.exists():
                    remainder = str(Path(*parts[i:]))
                    return list(glob_base.glob(remainder))
                return []
            glob_base = glob_base / part

    if base_path.exists():
        return [base_path]
    return [base_path] if include_nonexistent else []


def pattern_to_regex(pattern: str, *, posix: bool = False) -> str | None:
    """Convert gitignore-style pattern to regex.

    Args:
        pattern: Gitignore-style pattern (e.g., "**/secret.txt")
        posix: If True, convert to POSIX ERE compatible regex.
               POSIX ERE doesn't support PCRE extensions like (?:...) or (?P<>...).

    Returns:
        Regex pattern string, or None if pattern has no wildcards.
    """
    expanded = str(Path(pattern).expanduser())
    is_absolute = expanded.startswith("/")
    git_pattern = GitWildMatchPattern(expanded)

    if not git_pattern.regex:
        return None

    regex = git_pattern.regex.pattern
    if is_absolute and regex.startswith("^") and not regex.startswith("^/"):
        regex = "^/" + regex[1:]

    if posix:
        # Convert PCRE regex to POSIX ERE:
        # 1. Named capture groups (?P<name>...) -> (...)
        # 2. Non-capturing groups (?:...) -> (...)
        regex = re.sub(r"\(\?P<[^>]+>", "(", regex)
        regex = regex.replace("(?:", "(")

    return regex


def matches_hidden(
    path: str | Path, hidden_patterns: list[str], working_dir: Path
) -> bool:
    """Check if a path matches any hidden pattern."""
    path = Path(path).expanduser().resolve()

    for pattern in hidden_patterns:
        expanded = Path(pattern).expanduser()

        if "*" in pattern:
            # For glob patterns, use the original pattern string for matching
            check_path = path
            while check_path != check_path.parent:
                if check_path.match(pattern):
                    return True
                check_path = check_path.parent
        else:
            # For literal paths, resolve relative patterns against working_dir
            if not expanded.is_absolute():
                expanded = working_dir / expanded
            pattern_path = expanded.resolve() if expanded.exists() else expanded
            try:
                path.relative_to(pattern_path)
                return True
            except ValueError:
                if path == pattern_path:
                    return True
    return False
