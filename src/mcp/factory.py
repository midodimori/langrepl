from typing import Any

from src.core.config import MCPConfig
from src.core.settings import settings
from src.mcp.client import MCPClient


class MCPFactory:
    def __init__(
        self,
        enable_approval: bool = True,
    ):
        self.enable_approval = enable_approval
        self._client: MCPClient | None = None
        self._config_hash: int | None = None

    @staticmethod
    def _get_config_hash(config: MCPConfig) -> int:
        return hash(
            (
                tuple(sorted(config.servers.keys())),
                tuple(
                    sorted(
                        (k, v.enabled, v.command, tuple(v.args or []))
                        for k, v in config.servers.items()
                    )
                ),
            )
        )

    async def create(self, config: MCPConfig) -> "MCPClient":
        config_hash = self._get_config_hash(config)
        if self._client and self._config_hash == config_hash:
            return self._client

        server_config = {}
        tool_filters = {}
        repair_commands = {}

        for name, server in config.servers.items():
            # Skip disabled servers
            if not server.enabled:
                continue

            env = dict(server.env) if server.env else {}

            # Inject proxy settings if available
            http_proxy = settings.llm.http_proxy.get_secret_value()
            https_proxy = settings.llm.https_proxy.get_secret_value()

            if http_proxy:
                env.setdefault("HTTP_PROXY", http_proxy)
                env.setdefault("http_proxy", http_proxy)

            if https_proxy:
                env.setdefault("HTTPS_PROXY", https_proxy)
                env.setdefault("https_proxy", https_proxy)

            # Connection configuration (no tool filtering)
            server_dict: dict[str, Any] = {
                "transport": server.transport,
            }

            # Add transport-specific fields
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

            # Store repair command if available
            if server.repair_command:
                repair_commands[name] = server.repair_command

            # Tool filtering configuration
            if server.include or server.exclude:
                tool_filters[name] = {
                    "include": server.include,
                    "exclude": server.exclude,
                }

        self._client = MCPClient(
            server_config,
            tool_filters,
            repair_commands=repair_commands,
            enable_approval=self.enable_approval,
        )
        self._config_hash = config_hash
        return self._client
