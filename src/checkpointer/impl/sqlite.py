"""Async SQLite checkpointer implementation with message indexing."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from langchain_core.messages import AnyMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata, CheckpointTuple
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.checkpointer.base import BaseCheckpointer, HumanMessageEntry
from src.core.logging import get_logger

logger = get_logger(__name__)


class IndexedAsyncSqliteSaver(AsyncSqliteSaver, BaseCheckpointer):
    """AsyncSqliteSaver with automatic message indexing for performance."""

    async def setup(self) -> None:
        """Initialize tables including message index table."""
        await super().setup()

        async with self.lock:
            await self.conn.executescript(
                """
            CREATE TABLE IF NOT EXISTS checkpoint_messages (
                thread_id TEXT NOT NULL,
                checkpoint_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                message_idx INTEGER NOT NULL,
                message_type TEXT NOT NULL,
                message_preview TEXT,
                PRIMARY KEY (thread_id, checkpoint_id, message_idx)
            );
            CREATE INDEX IF NOT EXISTS idx_thread_ns_messages
                ON checkpoint_messages(thread_id, checkpoint_ns, message_type);
            CREATE INDEX IF NOT EXISTS idx_thread_lookup
                ON checkpoints(thread_id, checkpoint_ns);
            CREATE INDEX IF NOT EXISTS idx_checkpoint_id
                ON checkpoints(checkpoint_id);
            """
            )
            await self.conn.commit()

        logger.debug("Message index tables and indices created")

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict[str, int | float | str],
    ) -> RunnableConfig:
        """Save checkpoint and update message index."""
        result = await super().aput(config, checkpoint, metadata, new_versions)
        await self._index_messages(config, checkpoint)
        return result

    async def _index_messages(
        self, config: RunnableConfig, checkpoint: Checkpoint
    ) -> None:
        """Extract and index messages from checkpoint."""
        try:
            thread_id = config["configurable"].get("thread_id")
            checkpoint_id = checkpoint.get("id")
            checkpoint_ns = config["configurable"].get("checkpoint_ns", "")

            if not thread_id or not checkpoint_id:
                return

            messages = checkpoint.get("channel_values", {}).get("messages", [])
            if not messages:
                return

            async with self.lock:
                await self.conn.execute(
                    "DELETE FROM checkpoint_messages WHERE thread_id = ? AND checkpoint_id = ?",
                    (thread_id, checkpoint_id),
                )

                rows = [
                    (
                        thread_id,
                        checkpoint_id,
                        checkpoint_ns,
                        idx,
                        msg.type,
                        self._get_message_preview(msg),
                    )
                    for idx, msg in enumerate(messages)
                ]

                await self.conn.executemany(
                    """
                    INSERT OR REPLACE INTO checkpoint_messages
                    (thread_id, checkpoint_id, checkpoint_ns, message_idx, message_type, message_preview)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

                await self.conn.commit()

            logger.debug(
                f"Indexed {len(messages)} messages for thread {thread_id}, checkpoint {checkpoint_id}"
            )

        except Exception as e:
            logger.warning(f"Failed to index messages: {e}")

    async def get_threads(self) -> set[str]:
        """Get all thread IDs."""
        try:
            async with self.lock:
                cursor = await self.conn.execute(
                    "SELECT DISTINCT thread_id FROM checkpoints WHERE checkpoint_ns = ''"
                )
                rows = await cursor.fetchall()

            return {row[0] for row in rows if row[0]}

        except Exception as e:
            logger.error(f"Failed to get thread IDs: {e}")
            return set()

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
        checkpoint_ns = latest.config.get("configurable", {}).get("checkpoint_ns", "")

        # Check if indexed
        async with self.lock:
            cursor = await self.conn.execute(
                "SELECT COUNT(*) FROM checkpoint_messages WHERE thread_id = ? AND checkpoint_ns = ?",
                (thread_id, checkpoint_ns),
            )
            row = await cursor.fetchone()
            has_index = row and row[0] > 0

        # Lazy index if needed
        if not has_index:
            if on_indexing:
                on_indexing()

            logger.debug(f"Indexing thread {thread_id} namespace {checkpoint_ns!r}...")
            history = await self.get_history(latest)

            for checkpoint_tuple in history:
                checkpoint = checkpoint_tuple.checkpoint
                if checkpoint:
                    config = RunnableConfig(
                        configurable={
                            "thread_id": checkpoint_tuple.config.get(
                                "configurable", {}
                            ).get("thread_id"),
                            "checkpoint_ns": checkpoint_tuple.config.get(
                                "configurable", {}
                            ).get("checkpoint_ns", ""),
                        }
                    )
                    await self._index_messages(config, checkpoint)

            logger.debug(
                f"Indexing complete for {thread_id} namespace {checkpoint_ns!r}"
            )

        # Build mapping of message index -> checkpoint_id using the index
        # Query: for each unique checkpoint, get the max message_idx (= message count)
        # Filter by namespace to only get checkpoints from the current branch
        checkpoint_by_msg_count = {}
        async with self.lock:
            cursor = await self.conn.execute(
                """
                SELECT checkpoint_id, MAX(message_idx) + 1 as msg_count
                FROM checkpoint_messages
                WHERE thread_id = ? AND checkpoint_ns = ?
                GROUP BY checkpoint_id
                ORDER BY msg_count
                """,
                (thread_id, checkpoint_ns),
            )
            rows = await cursor.fetchall()

        for checkpoint_id, msg_count in rows:
            checkpoint_by_msg_count[msg_count] = checkpoint_id

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
        """Delete checkpoints after checkpoint_id. Returns count deleted."""
        # Get checkpoint IDs to delete
        if checkpoint_id is None:
            checkpoints_to_delete = await self._get_all_checkpoint_ids(thread_id)
        else:
            checkpoints_to_delete = await self._get_checkpoints_after(
                thread_id, checkpoint_id
            )

        if not checkpoints_to_delete:
            return 0

        # Delete them
        async with self.lock:
            placeholders = ",".join(["?"] * len(checkpoints_to_delete))
            await self.conn.execute(
                f"DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_id IN ({placeholders})",
                (thread_id, *checkpoints_to_delete),
            )
            await self.conn.execute(
                f"DELETE FROM writes WHERE thread_id = ? AND checkpoint_id IN ({placeholders})",
                (thread_id, *checkpoints_to_delete),
            )
            await self.conn.execute(
                f"DELETE FROM checkpoint_messages WHERE thread_id = ? AND checkpoint_id IN ({placeholders})",
                (thread_id, *checkpoints_to_delete),
            )
            await self.conn.commit()

        return len(checkpoints_to_delete)

    async def _get_all_checkpoint_ids(self, thread_id: str) -> list[str]:
        """Get all checkpoint IDs for a thread."""
        async with self.lock:
            cursor = await self.conn.execute(
                "SELECT checkpoint_id FROM checkpoints WHERE thread_id = ?",
                (thread_id,),
            )
            rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def _get_checkpoints_after(
        self, thread_id: str, checkpoint_id: str
    ) -> list[str]:
        """Get checkpoint IDs after checkpoint_id. Uses index if available."""
        # Try index-based lookup
        async with self.lock:
            cursor = await self.conn.execute(
                "SELECT MAX(message_idx) + 1, checkpoint_ns FROM checkpoint_messages WHERE thread_id = ? AND checkpoint_id = ?",
                (thread_id, checkpoint_id),
            )
            row = await cursor.fetchone()

        if row and row[0] is not None:
            # Fast path: use index, filter by namespace to stay in same branch
            target_msg_count = row[0]
            checkpoint_ns = row[1]
            async with self.lock:
                cursor = await self.conn.execute(
                    """
                    SELECT DISTINCT checkpoint_id FROM checkpoint_messages
                    WHERE thread_id = ? AND checkpoint_ns = ?
                    GROUP BY checkpoint_id
                    HAVING MAX(message_idx) + 1 > ?
                    """,
                    (thread_id, checkpoint_ns, target_msg_count),
                )
                rows = await cursor.fetchall()
            return [row[0] for row in rows]

        # Slow path: walk history
        config = RunnableConfig(configurable={"thread_id": thread_id})
        latest = await self.aget_tuple(config)
        if not latest:
            return []

        history = await self.get_history(latest)
        idx = next(
            (
                i
                for i, cp in enumerate(history)
                if cp.checkpoint.get("id") == checkpoint_id
            ),
            None,
        )
        if idx is None:
            return []

        return [
            cp_id for cp in history[idx + 1 :] if (cp_id := cp.checkpoint.get("id"))
        ]

    @staticmethod
    def _get_message_preview(msg: AnyMessage) -> str:
        """Get truncated message preview."""
        try:
            text = getattr(msg, "short_content", None) or getattr(msg, "text", "")
            if isinstance(text, list):
                text = " ".join(str(item) for item in text)
            text = str(text).replace("\n", " ")
            return text[:100]
        except Exception:
            return ""


class AsyncSqliteCheckpointer:
    """Wrapper for IndexedAsyncSqliteSaver with connection management."""

    @staticmethod
    @asynccontextmanager
    async def create(
        connection_string: str,
    ) -> AsyncIterator[IndexedAsyncSqliteSaver]:
        """Create an async SQLite checkpointer with indexing and connection management.

        Args:
            connection_string: SQLite database file path or ":memory:" for in-memory

        Yields:
            IndexedAsyncSqliteSaver: The configured checkpointer instance
        """
        logger.debug(
            f"Creating indexed SQLite checkpointer with connection: {connection_string}"
        )

        try:
            async with IndexedAsyncSqliteSaver.from_conn_string(
                connection_string
            ) as saver:
                await saver.setup()
                logger.debug("Indexed SQLite checkpointer created successfully")
                yield saver  # type: ignore[misc]
        except Exception as e:
            logger.error(f"Failed to create SQLite checkpointer: {e}")
            raise
