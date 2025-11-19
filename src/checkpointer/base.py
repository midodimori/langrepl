"""Base checkpointer with extended methods for langrepl."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import BaseMessage
from langgraph.checkpoint.base import BaseCheckpointSaver as _BaseCheckpointSaver
from langgraph.checkpoint.base import CheckpointTuple


@dataclass
class HumanMessageEntry:
    """Human message with replay metadata."""

    text: str
    reference_mapping: dict[str, Any]
    messages_before_count: int
    checkpoint_id: str | None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_cost: float | None = None


class BaseCheckpointer(_BaseCheckpointSaver):
    """Base checkpointer with additional query methods."""

    async def get_threads(self) -> set[str]:
        """Get all thread IDs."""
        raise NotImplementedError

    async def get_history(self, latest: CheckpointTuple) -> list[CheckpointTuple]:
        """Get checkpoint history in chronological order (oldest first)."""
        raise NotImplementedError

    async def delete_after(self, thread_id: str, checkpoint_id: str | None) -> int:
        """Delete checkpoints after checkpoint_id. Returns count deleted."""
        raise NotImplementedError

    async def get_human_messages(
        self,
        thread_id: str,
        latest: CheckpointTuple,
        on_indexing: Callable[[], None] | None = None,
    ) -> tuple[list[HumanMessageEntry], list[BaseMessage]]:
        """Get human messages with replay metadata.

        Returns:
            Tuple of (human_messages, all_messages)
        """
        raise NotImplementedError
