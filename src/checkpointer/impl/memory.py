"""In-memory checkpointer implementation."""

from collections.abc import Callable

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import CheckpointTuple
from langgraph.checkpoint.memory import MemorySaver

from src.checkpointer.base import BaseCheckpointer, HumanMessageEntry
from src.core.logging import get_logger

logger = get_logger(__name__)


class MemoryCheckpointer(MemorySaver, BaseCheckpointer):
    """In-memory checkpointer that extends LangGraph's MemorySaver.

    This implementation stores checkpoints in memory and does not persist
    across application restarts. Useful for development and testing.
    """

    def __init__(self):
        """Initialize the memory checkpointer."""
        super().__init__()
        logger.debug("Memory checkpointer initialized")

    def delete_checkpoints(
        self, thread_id: str, checkpoint_ns: str, checkpoint_ids: list[str]
    ) -> int:
        """Delete specific checkpoints from memory storage.

        Args:
            thread_id: Thread ID
            checkpoint_ns: Checkpoint namespace
            checkpoint_ids: List of checkpoint IDs to delete

        Returns:
            Number of checkpoints deleted
        """
        deleted_count = 0

        # MemorySaver stores checkpoints as: storage[thread_id][checkpoint_ns][checkpoint_id]
        if thread_id in self.storage and checkpoint_ns in self.storage[thread_id]:
            for checkpoint_id in checkpoint_ids:
                if checkpoint_id in self.storage[thread_id][checkpoint_ns]:
                    del self.storage[thread_id][checkpoint_ns][checkpoint_id]
                    deleted_count += 1
                    logger.debug(
                        f"Deleted checkpoint {checkpoint_id} from thread {thread_id}"
                    )

        # Also delete from writes: writes[(thread_id, checkpoint_ns, checkpoint_id)]
        for checkpoint_id in checkpoint_ids:
            write_key = (thread_id, checkpoint_ns, checkpoint_id)
            if write_key in self.writes:
                del self.writes[write_key]

        return deleted_count

    async def get_threads(self) -> set[str]:
        """Get all thread IDs."""
        return set(self.storage.keys())

    async def get_history(self, latest: CheckpointTuple) -> list[CheckpointTuple]:
        """Get checkpoint history in chronological order (oldest first)."""
        history = []
        current: CheckpointTuple | None = latest

        while current is not None:
            history.append(current)
            current = (
                await self.aget_tuple(current.parent_config)
                if current.parent_config
                else None
            )

        history.reverse()
        return history

    async def delete_after(self, thread_id: str, checkpoint_id: str | None) -> int:
        """Delete all checkpoints after checkpoint_id across all namespaces."""
        config = RunnableConfig(configurable={"thread_id": thread_id})
        latest = await self.aget_tuple(config)
        if not latest:
            return 0

        history = await self.get_history(latest)

        idx = (
            -1
            if checkpoint_id is None
            else next(
                (
                    i
                    for i, cp in enumerate(history)
                    if cp.checkpoint.get("id") == checkpoint_id
                ),
                None,
            )
        )
        if idx is None:
            return 0

        to_delete = history[idx + 1 :]
        if not to_delete:
            return 0

        checkpoint_ids_in_history = {
            cp_id for cp in to_delete if (cp_id := cp.checkpoint.get("id"))
        }

        total_deleted = 0
        if thread_id in self.storage:
            for ns in list(self.storage[thread_id].keys()):
                ns_checkpoints = list(self.storage[thread_id][ns].keys())

                to_delete_in_ns = [
                    cp_id
                    for cp_id in ns_checkpoints
                    if cp_id in checkpoint_ids_in_history or checkpoint_id is None
                ]

                if to_delete_in_ns or checkpoint_id is None:
                    if checkpoint_id is None:
                        to_delete_in_ns = ns_checkpoints

                    deleted = self.delete_checkpoints(thread_id, ns, to_delete_in_ns)
                    total_deleted += deleted

        return total_deleted

    async def get_human_messages(
        self,
        thread_id: str,
        latest: CheckpointTuple,
        on_indexing: Callable[[], None] | None = None,
    ) -> tuple[list[HumanMessageEntry], list[BaseMessage]]:
        """Get human messages with replay metadata."""
        if not latest or not latest.checkpoint:
            return [], []

        all_messages = latest.checkpoint.get("channel_values", {}).get("messages", [])
        channel_values = latest.checkpoint.get("channel_values", {})

        checkpoint_history = await self.get_history(latest)
        checkpoint_by_msg_count = {}
        for checkpoint_tuple in checkpoint_history:
            checkpoint = checkpoint_tuple.checkpoint
            if checkpoint and "channel_values" in checkpoint:
                msg_count = len(checkpoint["channel_values"].get("messages", []))
                checkpoint_by_msg_count[msg_count] = checkpoint.get("id")

        human_messages = []
        for i, msg in enumerate(all_messages):
            if msg.type == "human":
                human_messages.append(
                    HumanMessageEntry(
                        text=getattr(msg, "short_content", None) or msg.text,
                        reference_mapping=msg.additional_kwargs.get(
                            "reference_mapping", {}
                        ),
                        messages_before_count=i,
                        checkpoint_id=checkpoint_by_msg_count.get(i),
                        input_tokens=channel_values.get("current_input_tokens"),
                        output_tokens=channel_values.get("current_output_tokens"),
                        total_cost=channel_values.get("total_cost"),
                    )
                )

        return human_messages, all_messages
