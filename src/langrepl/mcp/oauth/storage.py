"""File-based OAuth token storage for MCP servers."""

from __future__ import annotations

import asyncio
import json
import os
import stat
from pathlib import Path
from typing import TypeVar

from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import BaseModel

from langrepl.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class FileTokenStorage:
    """File-based storage for OAuth tokens and client info.

    Implements the mcp.client.auth.TokenStorage protocol.
    Stores tokens in {base_dir}/{server_name}/ with atomic writes.
    """

    def __init__(self, base_dir: Path, server_name: str) -> None:
        self._dir = base_dir / server_name
        self._tokens_path = self._dir / "tokens.json"
        self._client_info_path = self._dir / "client_info.json"

    async def get_tokens(self) -> OAuthToken | None:
        """Load stored OAuth tokens."""
        return await self._load(self._tokens_path, OAuthToken)

    async def set_tokens(self, tokens: OAuthToken) -> None:
        """Store OAuth tokens."""
        await self._save(self._tokens_path, tokens)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        """Load stored client registration info."""
        return await self._load(self._client_info_path, OAuthClientInformationFull)

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        """Store client registration info."""
        await self._save(self._client_info_path, client_info)

    async def _load(self, path: Path, model: type[T]) -> T | None:
        """Load and validate a model from JSON file."""
        if not await asyncio.to_thread(path.exists):
            return None

        try:
            content = await asyncio.to_thread(path.read_text)
            data = json.loads(content)
            return model.model_validate(data)
        except Exception as e:
            logger.warning("Failed to load OAuth data from %s: %s", path, e)
            return None

    async def _save(
        self, path: Path, model: OAuthToken | OAuthClientInformationFull
    ) -> None:
        """Save a model to JSON file with atomic write."""
        try:
            await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
            content = model.model_dump_json(indent=2)

            # Atomic write using temp file with restrictive permissions
            temp_file = path.with_suffix(f".{os.getpid()}.tmp")
            try:
                await asyncio.to_thread(temp_file.write_text, content)
                await asyncio.to_thread(temp_file.chmod, stat.S_IRUSR | stat.S_IWUSR)
                await asyncio.to_thread(temp_file.replace, path)
            except Exception:
                if await asyncio.to_thread(temp_file.exists):
                    await asyncio.to_thread(temp_file.unlink)
                raise
        except Exception as e:
            logger.warning("Failed to save OAuth data to %s: %s", path, e)
