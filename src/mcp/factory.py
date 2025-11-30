from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.core.settings import settings
from src.mcp.client import MCPClient

if TYPE_CHECKING:
    from src.core.config import MCPConfig, MCPServerConfig


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
    ) -> MCPClient:
        config_hash = self._get_config_hash(config, cache_dir)
        if self._client and self._config_hash == config_hash:
            return self._client

        server_config = {}
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

            server_dict: dict[str, Any] = {
                "transport": server.transport,
            }

            if server.transport == "stdio":
                if server.command:
                    server_dict["command"] = server.command
                server_dict["args"] = server.args
                server_dict["env"] = env
            elif server.transport == "streamable_http":
                if server.url:
                    server_dict["url"] = server.url
                    if server.headers:
                        server_dict["headers"] = server.headers

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
