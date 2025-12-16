from pathlib import Path


def resolve_path(working_dir: str, path: str) -> Path:
    """Resolve a path relative to working directory if not absolute.

    Args:
        working_dir: The working directory to resolve relative paths against
        path: The path to resolve (can be relative, absolute, or '/')

    Returns:
        Resolved absolute Path object

    Special cases:
        - '/' is treated as the working directory itself, not system root
        - Absolute paths are used as-is
        - Relative paths are resolved against working directory
    """
    working_path = Path(working_dir).resolve()

    if path == "/":
        return working_path

    if Path(path).is_absolute():
        return Path(path).resolve()

    return (working_path / path).resolve()
