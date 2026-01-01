"""Lazy MCP tool proxy."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import jsonschema
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool, ToolException

from langrepl.core.logging import get_logger
from langrepl.tools.schema import ToolSchema

logger = get_logger(__name__)


class MCPTool(BaseTool):
    """Lazy MCP tool that hydrates on first invocation."""

    def __init__(
        self,
        server: str,
        schema: ToolSchema,
        loader: Callable[[str, str], Awaitable[BaseTool | None]],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            name=schema.name,
            description=schema.description,
            args_schema=schema.parameters,
            metadata=metadata,
        )
        self._server = server
        self._loader = loader
        self._schema = schema
        self._loaded: BaseTool | None = None
        self._lock: asyncio.Lock | None = None  # Lazy - created in current event loop

    async def _ensure(self) -> BaseTool:
        if self._loaded:
            return self._loaded

        # Create lock lazily in current event loop
        if self._lock is None:
            self._lock = asyncio.Lock()

        async with self._lock:
            if self._loaded:
                return self._loaded
            tool = await self._loader(self._server, self.name)
            if not tool:
                raise RuntimeError(
                    f"Failed to load MCP tool {self.name} from {self._server}"
                )
            self._loaded = tool

        return self._loaded

    def _validate(self, payload: Any) -> None:
        schema = self._schema.parameters
        if not schema:
            return
        try:
            jsonschema.validate(instance=payload, schema=schema)
        except jsonschema.ValidationError as e:
            raise ToolException(f"Invalid input for {self.name}: {e.message}") from e
        except jsonschema.SchemaError as e:
            logger.warning("Invalid schema for %s: %s", self.name, e)

    async def _arun(
        self,
        *args: Any,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> Any:
        tool = await self._ensure()

        payload = dict(kwargs)
        payload.pop("run_manager", None)

        if payload:
            self._validate(payload)
            return await self._invoke(tool, payload)
        if args:
            self._validate(args[0])
            return await self._invoke(tool, args[0])

        self._validate({})
        return await self._invoke(tool, {})

    async def _invoke(self, tool: BaseTool, payload: Any) -> Any:
        timeout = (self.metadata or {}).get("timeout")
        if timeout is None:
            return await tool.ainvoke(payload)
        try:
            return await asyncio.wait_for(tool.ainvoke(payload), timeout=timeout)
        except TimeoutError as e:
            raise ToolException(f"Tool {self.name} timed out after {timeout}s") from e

    def _run(
        self,
        *args: Any,
        run_manager: CallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No running loop - safe to create new one (lock created there)
            return asyncio.run(self._arun(*args, **kwargs))
        raise RuntimeError("MCPTool._run cannot be called with running loop; use _arun")
