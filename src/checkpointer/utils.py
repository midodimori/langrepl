"""Checkpoint utilities for LangGraph state management."""

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
