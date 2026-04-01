"""Server configuration."""

from __future__ import annotations

import asyncio
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import Field

from langrepl.configs.base import VersionedConfig
from langrepl.core.constants import SERVER_CONFIG_VERSION


class ServerProtocol(str, Enum):
    AG = "ag"
    AGUI = "agui"
    LANGSMITH = "langsmith"


class ServerConfig(VersionedConfig):
    version: str = Field(
        default=SERVER_CONFIG_VERSION, description="Config schema version"
    )
    protocol: ServerProtocol = Field(
        default=ServerProtocol.AGUI, description="Server protocol"
    )
    backend_url: str = Field(
        default="http://0.0.0.0:8000", description="Backend server URL"
    )
    frontend_url: str = Field(
        default="http://localhost:3000",
        description="Frontend URL (only used with agui protocol)",
    )

    @property
    def host(self) -> str:
        return urlparse(self.backend_url).hostname or ""

    @property
    def port(self) -> int:
        return urlparse(self.backend_url).port or 0

    @property
    def ui_port(self) -> int:
        return urlparse(self.frontend_url).port or 0

    @classmethod
    def get_latest_version(cls) -> str:
        return SERVER_CONFIG_VERSION

    @classmethod
    async def from_yaml(cls, file_path: Path) -> ServerConfig:
        """Load server config from YAML file."""
        yaml_content = await asyncio.to_thread(file_path.read_text)
        data = yaml.safe_load(yaml_content)
        if not data:
            raise ValueError(f"Empty server config at {file_path}")
        return cls(**data)
