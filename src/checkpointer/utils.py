"""Checkpoint utilities for LangGraph state management."""

from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple


async def get_checkpoint_history(
    checkpointer: BaseCheckpointSaver, latest_checkpoint: CheckpointTuple
) -> list[CheckpointTuple]:
    """Follow the parent chain to get checkpoint history for current branch only.

    Args:
        checkpointer: The checkpointer instance
        latest_checkpoint: The most recent checkpoint to start from

    Returns:
        List of CheckpointTuple in chronological order (oldest first)
    """
    history = []
    current_checkpoint_tuple: CheckpointTuple | None = latest_checkpoint

    while current_checkpoint_tuple is not None:
        history.append(current_checkpoint_tuple)
        parent_config = current_checkpoint_tuple.parent_config
        if parent_config:
            current_checkpoint_tuple = await checkpointer.aget_tuple(parent_config)
        else:
            current_checkpoint_tuple = None

    # Reverse since we built newest to oldest
    history.reverse()
    return history


async def delete_checkpoints_after(
    checkpointer: BaseCheckpointSaver, thread_id: str, checkpoint_id: str | None
) -> int:
    """Delete all checkpoints after checkpoint_id in thread."""
    config = RunnableConfig(configurable={"thread_id": thread_id})
    latest = await checkpointer.aget_tuple(config)
    if not latest:
        return 0

    history = await get_checkpoint_history(checkpointer, latest)

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

    if not (hasattr(checkpointer, "conn") and hasattr(checkpointer, "lock")):
        raise NotImplementedError(
            f"Deletion not supported for {type(checkpointer).__name__}"
        )

    cp = cast(Any, checkpointer)
    async with cp.lock:
        for t in to_delete:
            cp_id = t.checkpoint.get("id")
            ns = t.config.get("configurable", {}).get("checkpoint_ns", "")
            await cp.conn.execute(
                "DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?",
                (thread_id, ns, cp_id),
            )
            await cp.conn.execute(
                "DELETE FROM writes WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?",
                (thread_id, ns, cp_id),
            )
        await cp.conn.commit()

    return len(to_delete)
