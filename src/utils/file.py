"""File utility functions."""

from pygments_cache import get_lexer_for_filename

from src.core.logging import get_logger

logger = get_logger(__name__)


def get_file_language(file_path: str) -> str:
    """Get file language based on file extension."""
    try:
        return get_lexer_for_filename(file_path).name
    except Exception:
        return "Plaintext"
