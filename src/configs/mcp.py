"""MCP (Model Context Protocol) configuration models."""

import json
from pathlib import Path
from typing import Any, cast

import aiofiles
from pydantic import BaseModel, Field

from src.configs.base import VersionedConfig
from src.configs.enums import SandboxPermission
from src.core.constants import CONFIG_MCP_FILE_NAME
from src.utils.render import render_templates

__all__ = [
    "MCPConfig",
    "MCPServerConfig",
]


class MCPServerConfig(VersionedConfig):
    command: str | None = Field(
        default=None, description="The command to execute the server"
    )
    url: str | None = Field(default=None, description="The URL of the server")
    headers: dict[str, str] | None = Field(
        default=None, description="Headers for the server connection"
    )
    args: list[str] = Field(
        default_factory=list, description="Arguments for the server command"
    )
    transport: str = Field(default="stdio", description="Transport protocol")
    env: dict[str, str] = Field(
        default_factory=dict, description="Environment variables"
    )
    include: list[str] = Field(default_factory=list, description="Tools to include")
    exclude: list[str] = Field(default_factory=list, description="Tools to exclude")
    enabled: bool = Field(default=True, description="Whether the server is enabled")
    repair_command: list[str] | None = Field(
        default=None,
        description="Command list to run if server initialization fails",
    )
    sandbox_permissions: list[SandboxPermission] = Field(
        default_factory=list,
        description="Permissions this MCP server requires (deny-by-default if empty)",
    )


class MCPConfig(BaseModel):
    servers: dict[str, MCPServerConfig] = Field(
        default_factory=dict, description="MCP server configurations"
    )

    @classmethod
    async def from_json(
        cls, working_dir: Path, context: dict[str, Any] | None = None
    ) -> "MCPConfig":
        """Load MCP configuration from JSON file with template rendering.

        Args:
            working_dir: Working directory containing config
            context: Context variables for template rendering

        Returns:
            MCPConfig instance with rendered configuration
        """
        path = working_dir / CONFIG_MCP_FILE_NAME
        if not path.exists():
            return cls()
        context = context or {}
        async with aiofiles.open(path) as f:
            config_content = await f.read()

        try:
            config: dict[str, Any] = json.loads(config_content)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Failed to parse {path}: {e.msg}",
                e.doc,
                e.pos,
            ) from e
        rendered_config: dict = cast(dict, render_templates(config, context))
        mcp_servers = rendered_config.get("mcpServers", {})

        # Convert to our format
        servers = {}
        for name, server_config in mcp_servers.items():
            servers[name] = MCPServerConfig(**server_config)

        return cls(servers=servers)

    def to_json(self, working_dir: Path):
        """Save MCP configuration to JSON file."""
        path = working_dir / CONFIG_MCP_FILE_NAME
        # Convert to mcpServers format
        mcp_servers = {}
        for name, server_config in self.servers.items():
            mcp_servers[name] = server_config.model_dump()

        config = {"mcpServers": mcp_servers}

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(config, f, indent=2)
