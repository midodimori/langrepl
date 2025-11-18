"""Factory for creating checkpointer instances."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from src.checkpointer.base import BaseCheckpointer
from src.checkpointer.impl.memory import MemoryCheckpointer
from src.checkpointer.impl.sqlite import AsyncSqliteCheckpointer
from src.core.config import CheckpointerConfig, CheckpointerProvider


class CheckpointerFactory:
    """Factory for creating checkpointer instances."""

    def __init__(self):
        self._memory_instance: MemoryCheckpointer | None = None

    @asynccontextmanager
    async def create(
        self, config: CheckpointerConfig, database_url: str
    ) -> AsyncIterator[BaseCheckpointer]:
        """Create checkpointer based on config type."""
        if config.type == CheckpointerProvider.SQLITE:
            async with AsyncSqliteCheckpointer.create(
                connection_string=database_url,
            ) as checkpointer:
                yield checkpointer
        elif config.type == CheckpointerProvider.MEMORY:
            if self._memory_instance is None:
                self._memory_instance = MemoryCheckpointer()
            yield self._memory_instance
        else:
            raise ValueError(f"Unknown checkpointer provider: {config.type}")
