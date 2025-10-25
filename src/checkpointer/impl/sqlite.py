"""Async SQLite checkpointer implementation."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.core.logging import get_logger

logger = get_logger(__name__)


class AsyncSqliteCheckpointer:
    """Wrapper for LangGraph's AsyncSqliteSaver with connection management."""

    @staticmethod
    @asynccontextmanager
    async def create(
        connection_string: str,
        max_connections: int = 10,
    ) -> AsyncIterator[AsyncSqliteSaver]:
        """Create an async SQLite checkpointer with proper connection management.

        Args:
            connection_string: SQLite database file path or ":memory:" for in-memory
            max_connections: Maximum number of concurrent connections (unused for SQLite)

        Yields:
            AsyncSqliteSaver: The configured checkpointer instance
        """
        logger.debug(
            f"Creating SQLite checkpointer with connection: {connection_string}"
        )

        try:
            async with AsyncSqliteSaver.from_conn_string(connection_string) as saver:
                logger.debug("SQLite checkpointer created successfully")
                yield saver
        except Exception as e:
            logger.error(f"Failed to create SQLite checkpointer: {e}")
            raise
