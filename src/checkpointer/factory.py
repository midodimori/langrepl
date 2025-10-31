"""Factory for creating checkpointer instances."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.base import BaseCheckpointSaver

from src.checkpointer.impl.memory import MemoryCheckpointer
from src.checkpointer.impl.sqlite import AsyncSqliteCheckpointer
from src.core.config import CheckpointerConfig, CheckpointerProvider


class CheckpointerFactory:
    """Factory for creating checkpointer instances."""

    @asynccontextmanager
    async def create(
        self, config: CheckpointerConfig, database_url: str
    ) -> AsyncIterator[BaseCheckpointSaver]:
        """Create checkpointer based on config type."""
        if config.type == CheckpointerProvider.SQLITE:
            async with AsyncSqliteCheckpointer.create(
                connection_string=database_url,
                max_connections=config.max_connections,
            ) as checkpointer:
                yield checkpointer
        elif config.type == CheckpointerProvider.MEMORY:
            yield MemoryCheckpointer()
        else:
            raise ValueError(f"Unknown checkpointer provider: {config.type}")
