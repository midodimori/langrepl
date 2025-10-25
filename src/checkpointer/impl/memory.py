"""In-memory checkpointer implementation."""

from langgraph.checkpoint.memory import MemorySaver

from src.core.logging import get_logger

logger = get_logger(__name__)


class MemoryCheckpointer(MemorySaver):
    """In-memory checkpointer that extends LangGraph's MemorySaver.

    This implementation stores checkpoints in memory and does not persist
    across application restarts. Useful for development and testing.
    """

    def __init__(self):
        """Initialize the memory checkpointer."""
        super().__init__()
        logger.debug("Memory checkpointer initialized")
