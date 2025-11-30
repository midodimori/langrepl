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

from src.core.logging import get_logger
from src.tools.schema import ToolSchema, parameters_to_model

logger = get_logger(__name__)


class LazyMCPTool(BaseTool):
    """Proxy MCP tool that hydrates on first invocation."""

    def __init__(
        self,
        server_name: str,
        tool_schema: ToolSchema,
        loader: Callable[[str, str], Awaitable[BaseTool | None]],
    ):
        super().__init__(
            name=tool_schema.name,
            description=tool_schema.description,
            args_schema=parameters_to_model(tool_schema.name, tool_schema.parameters),
        )
        self._server_name = server_name
        self._loader = loader
        self._tool_schema = tool_schema
        self._loaded: BaseTool | None = None
        self._load_lock: asyncio.Lock = asyncio.Lock()

    async def _ensure_tool(self) -> BaseTool:
        if self._loaded:
            return self._loaded
        async with self._load_lock:
            if not self._loaded:
                tool = await self._loader(self._server_name, self.name)
                if not tool:
                    raise RuntimeError(
                        f"Failed to load MCP tool {self.name} from {self._server_name}"
                    )
                self._loaded = tool
        return self._loaded

    def _validate_payload(self, payload: Any) -> None:
        schema = self._tool_schema.parameters
        if not schema:
            return
        try:
            jsonschema.validate(instance=payload, schema=schema)
        except jsonschema.ValidationError as exc:
            raise ToolException(
                f"Invalid input for tool {self.name}: {exc.message}"
            ) from exc
        except jsonschema.SchemaError as exc:
            logger.warning("Invalid JSON schema for tool %s: %s", self.name, exc)

    async def _arun(
        self,
        *args: Any,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> Any:
        tool = await self._ensure_tool()
        payload = dict(kwargs)
        payload.pop("run_manager", None)
        if payload:
            self._validate_payload(payload)
            return await tool.ainvoke(payload)
        if args:
            self._validate_payload(args[0])
            return await tool.ainvoke(args[0])
        self._validate_payload({})
        return await tool.ainvoke({})

    def _run(
        self,
        *args: Any,
        run_manager: CallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._arun(*args, **kwargs))
        raise RuntimeError(
            "LazyMCPTool._run cannot be called while an event loop is running; use _arun instead."
        )
