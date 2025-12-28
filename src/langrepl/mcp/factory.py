from __future__ import annotations

import hashlib
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langchain_mcp_adapters.sessions import Connection

from langrepl.core.constants import TOOL_CATEGORY_MCP
from langrepl.core.logging import get_logger
from langrepl.core.settings import settings
from langrepl.mcp.client import MCPClient
from langrepl.sandboxes.backends.base import SandboxBinding

if TYPE_CHECKING:
    from langrepl.configs import MCPConfig, MCPServerConfig

logger = get_logger(__name__)


class MCPFactory:
    def __init__(
        self,
        enable_approval: bool = True,
    ):
        self.enable_approval = enable_approval
        self._client: MCPClient | None = None
        self._config_hash: int | None = None

    @staticmethod
    def _compute_server_hash(server: MCPServerConfig) -> str:
        """Compute a hash of server config for cache invalidation."""
        signature: dict[str, Any] = {
            "enabled": server.enabled,
            "transport": server.transport,
            "command": server.command,
            "args": tuple(server.args or []),
            "url": server.url,
            "headers": tuple(sorted((server.headers or {}).items())),
            "env": tuple(sorted((server.env or {}).items())),
            "include": tuple(server.include or []),
            "exclude": tuple(server.exclude or []),
            "repair_command": tuple(server.repair_command or []),
        }
        return hashlib.sha256(repr(signature).encode("utf-8")).hexdigest()

    @classmethod
    def _get_config_hash(cls, config: MCPConfig, cache_dir: Path | None) -> int:
        server_hashes = tuple(
            sorted(
                (name, cls._compute_server_hash(server))
                for name, server in config.servers.items()
            )
        )
        return hash((server_hashes, str(cache_dir) if cache_dir else None))

    async def create(
        self,
        config: MCPConfig,
        cache_dir: Path | None = None,
        sandbox_bindings: list[SandboxBinding] | None = None,
    ) -> MCPClient:
        config_hash = self._get_config_hash(config, cache_dir)
        if self._client and self._config_hash == config_hash:
            return self._client

        server_config: dict[str, Connection] = {}
        tool_filters = {}
        repair_commands = {}
        server_hashes = {}

        for name, server in config.servers.items():
            if not server.enabled:
                continue

            env = dict(server.env) if server.env else {}

            http_proxy = settings.llm.http_proxy.get_secret_value()
            https_proxy = settings.llm.https_proxy.get_secret_value()

            if http_proxy:
                env.setdefault("HTTP_PROXY", http_proxy)
                env.setdefault("http_proxy", http_proxy)

            if https_proxy:
                env.setdefault("HTTPS_PROXY", https_proxy)
                env.setdefault("https_proxy", https_proxy)

            server_dict: Connection | None = None

            if server.transport == "stdio":
                if server.command:
                    command = server.command
                    args = server.args or []

                    # Match server against sandbox bindings
                    sandbox_backend = None
                    if sandbox_bindings:
                        for binding in sandbox_bindings:
                            if self._matches_mcp_pattern(name, binding.patterns):
                                sandbox_backend = binding.backend
                                break

                    # Apply sandbox wrapping
                    if sandbox_backend:
                        try:
                            wrapped = sandbox_backend.build_command(
                                [command] + args, extra_env=env
                            )
                            command = wrapped[0]
                            args = wrapped[1:] if len(wrapped) > 1 else []

                            # Auto-inject offline env vars if sandbox blocks network
                            if "*" not in sandbox_backend.config.network.remote:
                                env["NPM_CONFIG_OFFLINE"] = "true"
                                env["UV_OFFLINE"] = "1"
                        except Exception as e:
                            logger.warning(
                                f"Failed to apply sandbox to MCP server '{name}', skipping: {e}"
                            )
                            continue

                    server_dict = {
                        "transport": "stdio",
                        "command": command,
                        "args": args,
                        "env": env,
                    }
            elif server.transport == "streamable_http":
                if server.url:
                    server_dict = {
                        "transport": "streamable_http",
                        "url": server.url,
                        "headers": server.headers,
                    }

            if server_dict is None:
                continue

            server_config[name] = server_dict

            if server.repair_command:
                repair_commands[name] = server.repair_command

            if server.include or server.exclude:
                tool_filters[name] = {
                    "include": server.include,
                    "exclude": server.exclude,
                }

            server_hashes[name] = self._compute_server_hash(server)

        self._client = MCPClient(
            server_config,
            tool_filters,
            repair_commands=repair_commands,
            enable_approval=self.enable_approval,
            cache_dir=cache_dir,
            server_hashes=server_hashes,
        )
        self._config_hash = config_hash
        return self._client

    @staticmethod
    def _matches_mcp_pattern(server_name: str, patterns: list[str]) -> bool:
        """Check if MCP server matches any pattern (mcp:<server>:*)."""
        for pattern in patterns:
            parts = pattern.split(":")
            if len(parts) != 3:
                continue

            category_pattern, server_pattern, tool_pattern = parts
            if category_pattern == TOOL_CATEGORY_MCP:
                if tool_pattern != "*":
                    logger.warning(
                        f"Invalid MCP pattern '{pattern}': tool part must be '*'"
                    )
                    continue
                if fnmatch(server_name, server_pattern):
                    return True
        return False
