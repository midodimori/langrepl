"""Stateful MCP session management."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from langrepl.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractAsyncContextManager

    from mcp import ClientSession

    SessionFactory = Callable[[str], AbstractAsyncContextManager[ClientSession]]

logger = get_logger(__name__)


class MCPSessions:
    """Manages persistent sessions for stateful MCP servers."""

    def __init__(self, factory: SessionFactory, timeout: float = 5.0) -> None:
        self._factory = factory
        self._timeout = timeout
        self._sessions: dict[str, ClientSession] = {}
        self._tasks: dict[str, tuple[asyncio.Task[None], asyncio.Event]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._close_lock = asyncio.Lock()

    async def get(self, server: str) -> ClientSession:
        """Get or create a persistent session."""
        if server in self._sessions:
            return self._sessions[server]

        lock = self._locks.setdefault(server, asyncio.Lock())
        async with lock:
            if server in self._sessions:
                return self._sessions[server]
            return await self._create(server)

    async def _create(self, server: str) -> ClientSession:
        ready, stop = asyncio.Event(), asyncio.Event()
        error: list[BaseException | None] = [None]

        async def runner() -> None:
            try:
                async with self._factory(server) as session:
                    self._sessions[server] = session
                    ready.set()
                    await stop.wait()
            except BaseException as e:
                error[0] = e
                ready.set()
                raise
            finally:
                self._sessions.pop(server, None)

        task = asyncio.create_task(runner())
        self._tasks[server] = (task, stop)
        await ready.wait()

        if error[0]:
            self._tasks.pop(server, None)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            raise error[0]

        # Verify session was stored (handles race after ready but before store)
        if server not in self._sessions:
            raise RuntimeError(f"Session for {server} not established")

        return self._sessions[server]

    async def close(self, server: str) -> None:
        """Close a single session."""
        if server not in self._tasks:
            return
        task, stop = self._tasks.pop(server)
        await self._shutdown(server, task, stop)

    async def close_all(self) -> None:
        """Close all sessions in parallel."""
        async with self._close_lock:
            if not self._tasks:
                return
            tasks_copy = list(self._tasks.items())
            self._tasks.clear()
            await asyncio.gather(
                *(self._shutdown(name, task, stop) for name, (task, stop) in tasks_copy)
            )
            self._sessions.clear()

    async def _shutdown(
        self, name: str, task: asyncio.Task[None], stop: asyncio.Event
    ) -> None:
        stop.set()
        try:
            await asyncio.wait_for(task, timeout=self._timeout)
        except TimeoutError:
            logger.warning("Timeout closing session %s", name)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        except Exception as e:
            logger.warning("Error closing session %s: %s", name, e)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
