"""MCP tool schema disk cache."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING

from langrepl.core.constants import MCP_CACHE_VERSION
from langrepl.core.logging import get_logger

if TYPE_CHECKING:
    from langrepl.tools.schema import ToolSchema

logger = get_logger(__name__)


class MCPCache:
    """Disk-based tool schema cache with hash validation."""

    def __init__(self, dir: Path | None, hashes: dict[str, str]) -> None:
        self._dir = dir
        self._hashes = hashes

    def _path(self, server: str) -> Path | None:
        return self._dir / f"{server}.json" if self._dir else None

    async def load(self, server: str) -> list[ToolSchema] | None:
        """Load cached schemas if hash matches."""
        from langrepl.tools.schema import ToolSchema

        path = self._path(server)
        if not path:
            return None

        if not await asyncio.to_thread(path.exists):
            return None

        try:
            content = await asyncio.to_thread(path.read_text)
            data = json.loads(content)
            cache_version = "0.0.0"
            cache_hash = None
            tools_data = data

            if isinstance(data, dict):
                cache_version = data.get("version", "0.0.0")
                cache_hash = data.get("hash")
                tools_data = data.get("tools", [])

            # Invalidate cache if version mismatch
            if cache_version != MCP_CACHE_VERSION:
                return None

            expected = self._hashes.get(server)
            if expected and cache_hash != expected:
                return None

            return [ToolSchema.model_validate(item) for item in tools_data]
        except Exception as e:
            logger.warning("Failed to load cache for %s: %s", server, e)
            return None

    async def save(self, server: str, schemas: list[ToolSchema]) -> None:
        """Save schemas to disk with hash."""
        path = self._path(server)
        if not path:
            return

        try:
            await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
            data = {
                "version": MCP_CACHE_VERSION,
                "hash": self._hashes.get(server),
                "tools": [s.model_dump() for s in schemas],
            }
            content = json.dumps(data, ensure_ascii=True, indent=2)

            # Atomic write using temp file
            temp_file = path.with_suffix(".tmp")
            try:
                await asyncio.to_thread(temp_file.write_text, content)
                await asyncio.to_thread(temp_file.replace, path)
            except Exception:
                if await asyncio.to_thread(temp_file.exists):
                    await asyncio.to_thread(temp_file.unlink)
                raise
        except Exception as e:
            logger.warning("Failed to save cache for %s: %s", server, e)
